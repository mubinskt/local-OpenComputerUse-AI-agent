import json
import time
from pathlib import Path
from typing import Any, Dict, List

import mss
from PIL import Image
import pyautogui
import tkinter as tk

from config import LAST_ACTIONS_FILE, SCREENSHOT_FILE

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


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


def save_last_actions(actions: List[Dict[str, Any]]) -> None:
    with open(LAST_ACTIONS_FILE, "w", encoding="utf-8") as fh:
        json.dump({"actions": actions}, fh, indent=2)