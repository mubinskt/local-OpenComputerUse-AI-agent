import json
import time
from typing import Any, Dict, List

import pyautogui
import tkinter as tk

from config import LAST_ACTIONS_FILE


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
        seconds = float(action.get("seconds", action.get("time", 1.0)))
        time.sleep(seconds)
        return {"success": True, "message": f"wait {seconds}s"}

    raise ValueError(f"Unsupported action: {kind}")


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
            result = execute_action(action)
            output_text.insert(tk.END, f"{idx}. {result['message']}\n")
        output_text.insert(tk.END, "Execution complete.\n")
    except Exception as exc:
        from tkinter import messagebox
        messagebox.showerror("Execution error", str(exc))
        output_text.insert(tk.END, f"Execution error: {exc}\n")