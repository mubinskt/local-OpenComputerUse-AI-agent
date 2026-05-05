import json
import sys
import threading
import time
from pathlib import Path
from typing import List

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, scrolledtext

from action_executor import execute_plan, parse_actions, validate_action
from config import SCRIPTS_DIR, SCREENSHOT_FILE, SCREENSHOTS_DIR
from functional_test import run_functional_test
from ollama_client import build_prompt, call_ollama
from script_manager import get_script_files, load_script_text
from utils import append_screenshot_log, capture_screenshot, save_last_actions


def update_script_preview(script_preview_text, script_var):
    script_preview_text.config(state="normal")
    script_preview_text.delete("1.0", tk.END)
    selected_name = script_var.get()
    if selected_name:
        script_preview_text.insert(tk.END, load_script_text(SCRIPTS_DIR / selected_name))
    else:
        script_preview_text.insert(tk.END, "No script selected.")
    script_preview_text.config(state="disabled")


def run_generation(script_text: str, output_text, screenshot_label, root):
    try:
        if not script_text:
            raise ValueError("No script selected or the script is empty.")

        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, "Capturing screenshot...\n")
        timestamp = int(time.time())
        plan_screenshot = SCREENSHOTS_DIR / f"plan_generation_{timestamp}.png"
        metadata = capture_screenshot(root, filename=plan_screenshot)
        append_screenshot_log({
            "step": "plan_generation",
            "script": script_text,
            "screenshot": str(plan_screenshot),
            "timestamp": timestamp,
        })
        screenshot_img = Image.open(plan_screenshot)
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


def on_generate_click(script_var, output_area, screenshot_preview, root):
    selected_name = script_var.get()
    if not selected_name:
        messagebox.showwarning("Input required", "Please select a script from the scripts folder.")
        return
    script_path = SCRIPTS_DIR / selected_name
    script_text = load_script_text(script_path)
    if not script_text:
        messagebox.showwarning("Script empty", "Selected script is empty or could not be loaded.")
        return
    threading.Thread(target=run_generation, args=(script_text, output_area, screenshot_preview, root), daemon=True).start()


def on_execute_click(output_area):
    if messagebox.askyesno("Confirm", "Execute the current JSON action plan?"):
        execute_plan(output_area)


def on_run_functional_test_click(script_var, output_area, screenshot_label, root):
    selected_name = script_var.get()
    if not selected_name:
        messagebox.showwarning("Input required", "Please select a script from the scripts folder.")
        return
    script_path = SCRIPTS_DIR / selected_name
    script_text = load_script_text(script_path)
    if not script_text:
        messagebox.showwarning("Script empty", "Selected script is empty or could not be loaded.")
        return
    threading.Thread(target=run_functional_test, args=(script_text, output_area, screenshot_label, root), daemon=True).start()


def create_ui():
    root = tk.Tk()
    root.title("Local Desktop Action Agent")
    root.geometry("820x760")
    root.resizable(False, False)

    script_files = get_script_files()
    script_names = [path.name for path in script_files]
    script_var = tk.StringVar(value=script_names[0] if script_names else "")

    script_label = tk.Label(root, text="Select automation script:")
    script_label.pack(anchor="w", padx=12, pady=(12, 0))

    script_option = tk.OptionMenu(root, script_var, *script_names, command=lambda _: update_script_preview(script_preview_text, script_var))
    script_option.config(width=36)
    script_option.pack(anchor="w", padx=12)

    script_preview_label = tk.Label(root, text="Script preview:")
    script_preview_label.pack(anchor="w", padx=12, pady=(8, 0))

    script_preview_text = scrolledtext.ScrolledText(root, width=98, height=8, state="disabled")
    script_preview_text.pack(padx=12)

    controls_frame = tk.Frame(root)
    controls_frame.pack(fill="x", padx=12, pady=8)

    capture_button = tk.Button(controls_frame, text="Capture Screenshot & Generate Plan", command=lambda: on_generate_click(script_var, output_area, screenshot_preview, root))
    capture_button.pack(side="left")

    run_functional_button = tk.Button(controls_frame, text="Run Functional Test", command=lambda: on_run_functional_test_click(script_var, output_area, screenshot_preview, root))
    run_functional_button.pack(side="left", padx=8)

    execute_button = tk.Button(controls_frame, text="Execute Plan", command=lambda: on_execute_click(output_area))
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
        update_script_preview(script_preview_text, script_var)

    return root