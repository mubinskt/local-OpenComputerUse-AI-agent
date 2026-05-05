import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import mss
from PIL import Image
import pyautogui
import tkinter as tk

from config import LAST_ACTIONS_FILE, SCREENSHOT_FILE, SCREENSHOTS_DIR, SCREENSHOT_LOG_FILE

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def ensure_screenshot_dirs() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if not SCREENSHOT_LOG_FILE.exists():
        with open(SCREENSHOT_LOG_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh)


def capture_screenshot(root: Optional[tk.Tk] = None, filename: Optional[Path] = None, hide_root: bool = True) -> Dict[str, Any]:
    ensure_screenshot_dirs()
    if filename is None:
        filename = SCREENSHOT_FILE
    if hide_root and root is not None:
        root.withdraw()
        time.sleep(0.3)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        image = sct.grab(monitor)
        pillow = Image.frombytes("RGB", image.size, image.rgb)
        pillow.save(filename, format="PNG")
        width, height = image.size
    if hide_root and root is not None:
        root.deiconify()
    return {
        "path": str(filename),
        "width": width,
        "height": height,
    }


def append_screenshot_log(entry: Dict[str, Any]) -> None:
    ensure_screenshot_dirs()
    if SCREENSHOT_LOG_FILE.exists():
        with open(SCREENSHOT_LOG_FILE, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    if not isinstance(data, list):
        data = []
    data.append(entry)
    with open(SCREENSHOT_LOG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def save_last_actions(actions: List[Dict[str, Any]]) -> None:
    with open(LAST_ACTIONS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"actions": actions}, fh, indent=2)