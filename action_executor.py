import json
import re
import time
from typing import Any, Dict, List, Optional

import pyautogui
import tkinter as tk

from config import (
    BASE_SCREEN_HEIGHT,
    BASE_SCREEN_WIDTH,
    FLIP_Y,
    LAST_ACTIONS_FILE,
    SCREENSHOTS_DIR,
    SCALE_COORDINATES,
)
from utils import append_screenshot_log, capture_screenshot


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


def sanitize_json_text(text: str) -> str:
    # Remove invalid JSON escape sequences like \_ while preserving valid escapes.
    return re.sub(r'\\([^"\\/bfnrtu])', r'\1', text)


def parse_actions(text: str) -> List[Dict[str, Any]]:
    cleaned = extract_json(text)
    cleaned = sanitize_json_text(cleaned)
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


def normalize_keys(keys: Any) -> List[str]:
    if isinstance(keys, str):
        raw = keys.strip()
        if not raw:
            return []
        if "+" in raw:
            return [part.strip().lower() for part in raw.split("+") if part.strip()]
        return [raw.lower()]
    if isinstance(keys, list):
        normalized: List[str] = []
        for key in keys:
            if key is None:
                continue
            text = str(key).strip()
            if not text:
                continue
            if "+" in text:
                normalized.extend([part.strip().lower() for part in text.split("+") if part.strip()])
            else:
                normalized.append(text.lower())
        return normalized
    return []


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


def resolve_coordinates(action: Dict[str, Any]) -> Dict[str, int]:
    screen_size = pyautogui.size()
    screen_width = int(screen_size.width)
    screen_height = int(screen_size.height)

    if "target_image" in action:
        image_path = str(action["target_image"])
        if not image_path:
            raise ValueError("target_image must be a valid path")
        try:
            center = pyautogui.locateCenterOnScreen(image_path, confidence=0.9)
        except Exception as exc:
            raise RuntimeError(
                "Image-based location requires OpenCV support and a valid image file"
            ) from exc
        if center is None:
            raise ValueError(f"Could not find image on screen: {image_path}")
        return {"x": int(center.x), "y": int(center.y)}

    x = None
    y = None
    x_needs_scale = False
    y_needs_scale = False
    y_is_top_left = False

    if "x_right_percent" in action:
        x = int(round(float(action["x_right_percent"]) * screen_width / 100.0))
        x = screen_width - 1 - x
    elif "x_right" in action:
        x = int(action["x_right"])
        x_needs_scale = True
    elif "x_percent" in action:
        x = int(round(float(action["x_percent"]) * screen_width / 100.0))
    elif "x" in action:
        x = int(action["x"])
        x_needs_scale = True

    if "y_bottom_percent" in action:
        y = int(round(float(action["y_bottom_percent"]) * screen_height / 100.0))
        y = screen_height - 1 - y
    elif "y_bottom" in action:
        y = int(action["y_bottom"])
        y_needs_scale = True
    elif "y_percent" in action:
        y = int(round(float(action["y_percent"]) * screen_height / 100.0))
        y_is_top_left = True
    elif "y" in action:
        y = int(action["y"])
        y_needs_scale = True
        y_is_top_left = True

    if x is None or y is None:
        raise ValueError(
            "click, double_click, drag, and scroll actions require x/y coordinates, percentage targets, or image targets"
        )

    if SCALE_COORDINATES and BASE_SCREEN_WIDTH and BASE_SCREEN_HEIGHT:
        if x_needs_scale:
            x = int(round(x * screen_width / BASE_SCREEN_WIDTH))
        if y_needs_scale:
            y = int(round(y * screen_height / BASE_SCREEN_HEIGHT))

    if FLIP_Y and y_is_top_left:
        y = screen_height - 1 - y

    return {"x": x, "y": y}


def execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(action.get("action", "")).lower()

    if kind == "click":
        coords = resolve_coordinates(action)
        button = action.get("button", "left")
        pyautogui.click(x=coords["x"], y=coords["y"], button=button)
        return {"success": True, "message": f"click {coords['x']},{coords['y']} {button}"}

    if kind == "double_click":
        coords = resolve_coordinates(action)
        pyautogui.doubleClick(x=coords["x"], y=coords["y"])
        return {"success": True, "message": f"double_click {coords['x']},{coords['y']}"}

    if kind == "type":
        text = str(action.get("text", ""))
        pyautogui.write(text, interval=0.02)
        return {"success": True, "message": f"type {len(text)} chars"}

    if kind == "key_combo":
        keys = normalize_keys(action.get("keys", []))
        if len(keys) < 1:
            raise ValueError("key_combo requires a non-empty keys list")
        pyautogui.hotkey(*keys)
        return {"success": True, "message": f"key_combo {'+'.join(keys)}"}

    if kind == "key_press":
        keys = normalize_keys(action.get("keys", []))
        if len(keys) < 1:
            raise ValueError("key_press requires a non-empty keys list")
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return {"success": True, "message": f"key_press {' '.join(keys)}"}

    if kind == "scroll":
        clicks = int(action.get("clicks", 0))
        if "x" in action and "y" in action:
            coords = resolve_coordinates(action)
            pyautogui.moveTo(coords["x"], coords["y"])
        pyautogui.scroll(clicks)
        return {"success": True, "message": f"scroll {clicks}"}

    if kind == "drag":
        if "x1" not in action or "y1" not in action or "x2" not in action or "y2" not in action:
            raise ValueError("drag requires x1, y1, x2, and y2 coordinates")
        start = resolve_coordinates({"x": action["x1"], "y": action["y1"]})
        end = resolve_coordinates({"x": action["x2"], "y": action["y2"]})
        duration = float(action.get("duration", 0.4))
        pyautogui.moveTo(start["x"], start["y"])
        pyautogui.dragTo(end["x"], end["y"], duration=duration, button="left")
        return {"success": True, "message": f"drag {start['x']},{start['y']} -> {end['x']},{end['y']}"}

    if kind == "wait":
        seconds = float(action.get("seconds", action.get("time", 1.0)))
        time.sleep(seconds)
        return {"success": True, "message": f"wait {seconds}s"}

    raise ValueError(f"Unsupported action: {kind}")


def capture_action_step(step: int, action: Dict[str, Any]) -> None:
    filename = SCREENSHOTS_DIR / f"step_{step:02d}_{action.get('action', 'action')}.png"
    capture_screenshot(root=None, filename=filename, hide_root=False)
    append_screenshot_log({
        "step": step,
        "action": action,
        "screenshot": str(filename),
        "timestamp": int(time.time()),
    })


def execute_plan(output_text) -> None:
    try:
        if not LAST_ACTIONS_FILE.exists():
            from tkinter import messagebox
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
            capture_action_step(idx, action)
            result = execute_action(action)
            output_text.insert(tk.END, f"{idx}. {result['message']}\n")
        output_text.insert(tk.END, "Execution complete.\n")
    except Exception as exc:
        from tkinter import messagebox
        messagebox.showerror("Execution error", str(exc))
        output_text.insert(tk.END, f"Execution error: {exc}\n")