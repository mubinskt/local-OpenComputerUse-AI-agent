import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

from action_executor import execute_action, parse_actions, validate_action
from config import FUNCTIONAL_TEST_LOG_FILE, SCREENSHOTS_DIR
from ollama_client import call_ollama
from utils import append_screenshot_log, capture_screenshot, save_last_actions


def parse_functional_script(script_text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("SCREENSHOT"):
            label = ""
            if ":" in line:
                _, label = line.split(":", 1)
                label = label.strip()
            items.append({"type": "screenshot", "label": label or "screenshot"})
            continue
        if line.upper().startswith("WAIT"):
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)", line)
            seconds = float(match.group(1)) if match else 1.0
            items.append({"type": "wait", "seconds": seconds, "text": line})
            continue
        items.append({"type": "step", "text": line})
    return items


def append_functional_test_log(entry: Dict[str, Any]) -> None:
    if FUNCTIONAL_TEST_LOG_FILE.exists():
        with open(FUNCTIONAL_TEST_LOG_FILE, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    if not isinstance(data, list):
        data = []
    data.append(entry)
    with open(FUNCTIONAL_TEST_LOG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def build_functional_prompt(step_text: str, screenshot_path: str, width: int, height: int, remaining_steps: List[str]) -> str:
    remaining_text = "\n".join(remaining_steps) if remaining_steps else "None"
    return (
        "You are a local automation assistant executing a functional test. "
        "The current step is described below. Return only valid JSON with an ordered list of actions for this step. "
        "Do not include any explanation outside the JSON."
        "Screenshot metadata:\n"
        f"- path: {screenshot_path}\n"
        f"- resolution: {width}x{height}\n"
        "The screenshot is the current desktop. Use screen coordinates relative to this resolution.\n"
        "Supported actions: click, double_click, type, key_combo, key_press, scroll, drag, wait.\n"
        "Use keys as a JSON list for key actions, for example: {\"keys\": [\"enter\"]} or {\"keys\": [\"ctrl\", \"s\"]}.\n"
        "For wait, use the field \"seconds\" or \"time\" with a numeric duration.\n"
        "Do not use placeholder coordinates like 100,200 unless the target location can be inferred from the screenshot.\n"
        "Current functional test step:\n"
        f"{step_text}\n"
        "Remaining test steps:\n"
        f"{remaining_text}\n"
    )


def run_functional_test(script_text: str, output_text: tk.Text, screenshot_label: tk.Label, root: tk.Tk) -> None:
    items = parse_functional_script(script_text)
    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, "Starting functional test run...\n")

    current_screenshot: Optional[Path] = None
    last_step_success = True
    step_index = 0

    for idx, item in enumerate(items, start=1):
        if item["type"] == "screenshot":
            screenshot_path = SCREENSHOTS_DIR / f"screenshot_{idx:02d}_{item['label'].replace(' ', '_')}.png"
            metadata = capture_screenshot(root, filename=screenshot_path)
            append_screenshot_log({
                "step": idx,
                "type": "screenshot",
                "label": item.get("label"),
                "screenshot": str(screenshot_path),
                "timestamp": int(time.time()),
            })
            output_text.insert(tk.END, f"Captured screenshot: {screenshot_path}\n")
            screenshot_img = Image.open(screenshot_path)
            screenshot_img.thumbnail((360, 240))
            screenshot_photo = ImageTk.PhotoImage(screenshot_img)
            screenshot_label.config(image=screenshot_photo)
            screenshot_label.image = screenshot_photo
            current_screenshot = screenshot_path
            append_functional_test_log({
                "step": idx,
                "type": "screenshot",
                "label": item.get("label"),
                "status": "success",
                "screenshot": str(screenshot_path),
                "timestamp": int(time.time()),
            })
            continue

        if item["type"] == "wait":
            seconds = item["seconds"]
            output_text.insert(tk.END, f"Waiting {seconds} seconds...\n")
            time.sleep(seconds)
            append_functional_test_log({
                "step": idx,
                "type": "wait",
                "seconds": seconds,
                "status": "success",
                "timestamp": int(time.time()),
            })
            continue

        if item["type"] == "step":
            step_index += 1
            if current_screenshot is None:
                current_screenshot = SCREENSHOTS_DIR / f"context_step_{idx:02d}.png"
                metadata = capture_screenshot(root, filename=current_screenshot)
                append_screenshot_log({
                    "step": idx,
                    "type": "context",
                    "screenshot": str(current_screenshot),
                    "timestamp": int(time.time()),
                })
            else:
                metadata = capture_screenshot(root, filename=current_screenshot, hide_root=False)

            output_text.insert(tk.END, f"Processing step {step_index}: {item['text']}\n")
            remaining_steps = [remaining["text"] for remaining in items[idx:] if remaining["type"] == "step"]
            prompt = build_functional_prompt(item["text"], str(current_screenshot), metadata["width"], metadata["height"], remaining_steps)

            try:
                model_output = call_ollama(prompt)
                actions = parse_actions(model_output)
                for action in actions:
                    validate_action(action)
                save_last_actions(actions)
                action_results = []
                for action in actions:
                    result = execute_action(action)
                    action_results.append(result)
                append_functional_test_log({
                    "step": idx,
                    "type": "step",
                    "text": item["text"],
                    "status": "success",
                    "actions": actions,
                    "results": action_results,
                    "timestamp": int(time.time()),
                })
                output_text.insert(tk.END, f"Step {step_index} completed successfully.\n")
            except Exception as exc:
                append_functional_test_log({
                    "step": idx,
                    "type": "step",
                    "text": item["text"],
                    "status": "failure",
                    "error": str(exc),
                    "timestamp": int(time.time()),
                })
                output_text.insert(tk.END, f"Step {step_index} failed: {exc}\n")
                last_step_success = False
                break

    output_text.insert(tk.END, f"Functional test run completed. Success={last_step_success}\n")
