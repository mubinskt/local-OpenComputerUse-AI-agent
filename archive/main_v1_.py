import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import mss
import pyautogui
import requests
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, scrolledtext

# Local Ollama configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

BASE_DIR = Path(__file__).resolve().parent
LAST_ACTIONS_FILE = BASE_DIR / "last_actions.json"
SCREENSHOT_FILE = BASE_DIR / "screenshot.png"
SCRIPTS_DIR = BASE_DIR / "scripts"


def get_script_files() -> List[Path]:
    if not SCRIPTS_DIR.exists() or not SCRIPTS_DIR.is_dir():
        return []
    return sorted([path for path in SCRIPTS_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".txt"])


def load_script_text(script_path: Path) -> str:
    try:
        return script_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def update_script_preview() -> None:
    script_preview_text.config(state="normal")
    script_preview_text.delete("1.0", tk.END)
    selected_name = script_var.get()
    if selected_name:
        script_preview_text.insert(tk.END, load_script_text(SCRIPTS_DIR / selected_name))
    else:
        script_preview_text.insert(tk.END, "No script selected.")
    script_preview_text.config(state="disabled")


def capture_screenshot(root: tk.Tk) -> Dict[str, Any]:
    root.withdraw()
    time.sleep(0.3)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        image = sct.grab(monitor)
        pillow = Image.frombytes("RGB", image.size, image.rgb)
        pillow.save(SCREENSHOT_FILE, format="PNG")
        width, height = image.size
    root.deiconify()
    return {
        "path": str(SCREENSHOT_FILE),
        "width": width,
        "height": height,
    }


def build_prompt(script_text: str, width: int, height: int) -> str:
    return (
        "You are a local automation assistant. "
        "The user will provide a scripted set of desktop automation steps. "
        "Return only valid JSON with an ordered list of actions. "
        "Do not include any explanation outside the JSON object.\n"
        "Screenshot metadata:\n"
        f"- path: {SCREENSHOT_FILE}\n"
        f"- resolution: {width}x{height}\n"
        "The screenshot is the current desktop. Use screen coordinates relative to this resolution.\n"
        "Supported actions: click, double_click, type, key_combo, key_press, scroll, drag, wait.\n"
        "Output format:\n"
        "{\n  \"actions\": [\n    {\"action\": \"click\", \"x\": 100, \"y\": 200, \"button\": \"left\"},\n"
        "    {\"action\": \"type\", \"text\": \"hello world\"}\n"
        "  ]\n}\n"
        "Use the script text below as the instruction guide.\n"
        f"Script:\n{script_text}\n"
    )


def get_available_ollama_models() -> List[str]:
    endpoints = ["/api/tags", "/v1/models"]
    for endpoint in endpoints:
        try:
            response = requests.get(f"{OLLAMA_URL}{endpoint}", timeout=10)
            if response.status_code != 200:
                continue
            data = response.json()
        except requests.RequestException:
            continue

        if isinstance(data, dict):
            if "models" in data and isinstance(data["models"], list):
                return [str(item.get("name")) for item in data["models"] if isinstance(item, dict) and item.get("name")]
            if "data" in data and isinstance(data["data"], list):
                return [str(item.get("id")) for item in data["data"] if isinstance(item, dict) and item.get("id")]
    return []


def resolve_ollama_model() -> str:
    if not OLLAMA_MODEL:
        available = get_available_ollama_models()
        if available:
            return available[0]
        raise RuntimeError(
            "No Ollama model configured and no models were discovered at the Ollama endpoint. "
            f"Check OLLAMA_MODEL and Ollama URL {OLLAMA_URL}."
        )

    available = get_available_ollama_models()
    if available and OLLAMA_MODEL not in available:
        raise RuntimeError(
            f"Model '{OLLAMA_MODEL}' was not found in Ollama. Available models: {', '.join(available)}. "
            "Pull a model with `ollama pull <model>` or set OLLAMA_MODEL to one of the available names."
        )
    return OLLAMA_MODEL


def _parse_response_json(response: requests.Response) -> Dict[str, Any]:
    text = response.text.strip()
    if not text:
        raise RuntimeError(
            f"Ollama returned an empty response body (status={response.status_code}). "
            f"Check that the model and endpoint are correct."
        )
    try:
        return response.json()
    except ValueError:
        raise RuntimeError(
            f"Failed to parse Ollama response as JSON (status={response.status_code}).\n"
            f"Response body:\n{text[:2000]}"
        )


def _ollama_post(url: str, payload: Dict[str, Any]) -> requests.Response:
    try:
        response = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as exc:
        raise RuntimeError(f"Request to Ollama failed: {exc}")
    return response


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
        choice = data["choices"][0]
        if isinstance(choice, dict):
            if "message" in choice and isinstance(choice["message"], dict):
                return str(choice["message"].get("content", "")).strip()
            if "text" in choice:
                return str(choice["text"]).strip()
    if "text" in data:
        return str(data["text"]).strip()
    return ""


def call_ollama(prompt: str) -> str:
    model_name = resolve_ollama_model()
    chat_payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a JSON-only action planner."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    # Try chat endpoint first; fall back to prompt-style completion if empty or unsupported.
    chat_url = f"{OLLAMA_URL}/v1/chat/completions"
    response = _ollama_post(chat_url, chat_payload)
    if response.status_code < 400:
        data = _parse_response_json(response)
        text = _extract_text_from_response(data)
        if text:
            return text
        # Some Ollama models respond with an empty chat object; fall back to completions.

    complete_payload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": 0.2,
        "max_tokens": 600,
    }
    complete_url = f"{OLLAMA_URL}/v1/completions"
    response = _ollama_post(complete_url, complete_payload)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama completions endpoint failed: {response.status_code}: {response.text.strip()}"
        )
    data = _parse_response_json(response)
    text = _extract_text_from_response(data)
    if text:
        return text

    raise RuntimeError(
        f"Ollama did not return text. Response: {json.dumps(data, indent=2)[:2000]}"
    )


def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        return text[len("```json"):-3].strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_actions(text: str) -> List[Dict[str, Any]]:
    cleaned = extract_json(text)
    payload = json.loads(cleaned)
    if isinstance(payload, dict) and "actions" in payload:
        actions = payload["actions"]
    elif isinstance(payload, list):
        actions = payload
    else:
        raise ValueError("JSON must contain an actions list")
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    return actions


def validate_action(action: Dict[str, Any]) -> None:
    if not isinstance(action, dict):
        raise ValueError("Each action must be an object")
    if "action" not in action:
        raise ValueError("Every action requires an 'action' field")
    kind = str(action["action"]).lower()
    if kind not in {
        "click",
        "double_click",
        "type",
        "key_combo",
        "key_press",
        "scroll",
        "drag",
        "wait",
    }:
        raise ValueError(f"Unsupported action: {kind}")


def execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(action.get("action", "")).lower()

    if kind == "click":
        x = int(action["x"])
        y = int(action["y"])
        button = action.get("button", "left")
        pyautogui.click(x=x, y=y, button=button)
        return {"success": True, "message": f"click {x},{y} {button}"}

    if kind == "double_click":
        x = int(action["x"])
        y = int(action["y"])
        pyautogui.doubleClick(x=x, y=y)
        return {"success": True, "message": f"double_click {x},{y}"}

    if kind == "type":
        text = str(action.get("text", ""))
        pyautogui.write(text, interval=0.02)
        return {"success": True, "message": f"type {len(text)} chars"}

    if kind == "key_combo":
        keys = action.get("keys", [])
        if not isinstance(keys, list) or len(keys) < 1:
            raise ValueError("key_combo requires a non-empty keys list")
        pyautogui.hotkey(*[str(k) for k in keys])
        return {"success": True, "message": f"key_combo {'+'.join(keys)}"}

    if kind == "key_press":
        keys = action.get("keys", [])
        if not isinstance(keys, list) or len(keys) < 1:
            raise ValueError("key_press requires a non-empty keys list")
        for key in keys:
            pyautogui.press(str(key))
        return {"success": True, "message": f"key_press {' '.join(keys)}"}

    if kind == "scroll":
        clicks = int(action.get("clicks", 0))
        x = action.get("x")
        y = action.get("y")
        if x is not None and y is not None:
            pyautogui.moveTo(int(x), int(y))
        pyautogui.scroll(clicks)
        return {"success": True, "message": f"scroll {clicks}"}

    if kind == "drag":
        x1 = int(action["x1"])
        y1 = int(action["y1"])
        x2 = int(action["x2"])
        y2 = int(action["y2"])
        duration = float(action.get("duration", 0.4))
        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=duration, button="left")
        return {"success": True, "message": f"drag {x1},{y1} -> {x2},{y2}"}

    if kind == "wait":
        seconds = float(action.get("seconds", 1.0))
        time.sleep(seconds)
        return {"success": True, "message": f"wait {seconds}s"}

    raise ValueError(f"Unsupported action: {kind}")


def save_last_actions(actions: List[Dict[str, Any]]) -> None:
    with open(LAST_ACTIONS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"actions": actions}, fh, indent=2)


def run_generation(script_text: str, output_text: tk.Text, screenshot_label: tk.Label) -> None:
    try:
        if not script_text:
            raise ValueError("No script selected or the script is empty.")

        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, "Capturing screenshot...\n")
        metadata = capture_screenshot(root)
        screenshot_img = Image.open(SCREENSHOT_FILE)
        screenshot_img.thumbnail((360, 240))
        screenshot_photo = ImageTk.PhotoImage(screenshot_img)
        screenshot_label.config(image=screenshot_photo)
        screenshot_label.image = screenshot_photo

        prompt = build_prompt(script_text, metadata["width"], metadata["height"])
        output_text.insert(tk.END, "Sending prompt to Ollama...\n")
        sys.stdout.flush()

        model_output = call_ollama(prompt)
        output_text.insert(tk.END, f"Model output received.\n{model_output}\n\n")
        actions = parse_actions(model_output)
        for action in actions:
            validate_action(action)
        save_last_actions(actions)
        output_text.insert(tk.END, "Action plan loaded and saved to last_actions.json\n")
        output_text.insert(tk.END, json.dumps({"actions": actions}, indent=2))
        output_text.insert(tk.END, "\n\nClick EXECUTE when ready.\n")
    except Exception as exc:
        messagebox.showerror("Error", str(exc))
        output_text.insert(tk.END, f"Error: {exc}\n")


def execute_plan(output_text: tk.Text) -> None:
    try:
        if not LAST_ACTIONS_FILE.exists():
            messagebox.showwarning("No plan", "No saved action plan found.")
            return
        with open(LAST_ACTIONS_FILE, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        actions = payload.get("actions") if isinstance(payload, dict) else payload
        if not isinstance(actions, list):
            raise ValueError("The saved plan must contain an actions list")
        output_text.insert(tk.END, "\nExecuting actions...\n")
        for idx, action in enumerate(actions, start=1):
            validate_action(action)
            result = execute_action(action)
            output_text.insert(tk.END, f"{idx}. {result['message']}\n")
        output_text.insert(tk.END, "Execution complete.\n")
    except Exception as exc:
        messagebox.showerror("Execution error", str(exc))
        output_text.insert(tk.END, f"Execution error: {exc}\n")


def on_generate_click() -> None:
    selected_name = script_var.get()
    if not selected_name:
        messagebox.showwarning("Input required", "Please select a script from the scripts folder.")
        return
    script_path = SCRIPTS_DIR / selected_name
    script_text = load_script_text(script_path)
    if not script_text:
        messagebox.showwarning("Script empty", "Selected script is empty or could not be loaded.")
        return
    threading.Thread(target=run_generation, args=(script_text, output_area, screenshot_preview), daemon=True).start()


def on_execute_click() -> None:
    if messagebox.askyesno("Confirm", "Execute the current JSON action plan?"):
        execute_plan(output_area)


root = tk.Tk()
root.title("Local Desktop Action Agent")
root.geometry("820x760")
root.resizable(False, False)

script_files = get_script_files()
script_names = [path.name for path in script_files]
script_var = tk.StringVar(value=script_names[0] if script_names else "")

script_label = tk.Label(root, text="Select automation script:")
script_label.pack(anchor="w", padx=12, pady=(12, 0))

script_option = tk.OptionMenu(root, script_var, *script_names, command=lambda _: update_script_preview())
script_option.config(width=36)
script_option.pack(anchor="w", padx=12)

script_preview_label = tk.Label(root, text="Script preview:")
script_preview_label.pack(anchor="w", padx=12, pady=(8, 0))

script_preview_text = scrolledtext.ScrolledText(root, width=98, height=8, state="disabled")
script_preview_text.pack(padx=12)

controls_frame = tk.Frame(root)
controls_frame.pack(fill="x", padx=12, pady=8)

capture_button = tk.Button(controls_frame, text="Capture Screenshot & Generate Plan", command=on_generate_click)
capture_button.pack(side="left")

execute_button = tk.Button(controls_frame, text="Execute Plan", command=on_execute_click)
execute_button.pack(side="left", padx=8)

screenshot_preview = tk.Label(root, text="Screenshot preview will appear here.")
screenshot_preview.pack(padx=12, pady=8)

output_label = tk.Label(root, text="Action Plan / Model Output:")
output_label.pack(anchor="w", padx=12)

output_area = scrolledtext.ScrolledText(root, width=98, height=20)
output_area.pack(padx=12, pady=(0, 12))

footer = tk.Label(root, text="The app saves the latest plan to last_actions.json.")
footer.pack(anchor="w", padx=12, pady=(0, 12))

if not script_names:
    capture_button.config(state="disabled")
    script_preview_text.config(state="normal")
    script_preview_text.insert(tk.END, "No script files found in the scripts folder. Add .txt scripts and restart the app.")
    script_preview_text.config(state="disabled")
else:
    update_script_preview()

root.mainloop()
