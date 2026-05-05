import os
from pathlib import Path

# Local Ollama configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Screen coordinate scaling configuration
BASE_SCREEN_WIDTH = int(os.getenv("BASE_SCREEN_WIDTH", "1920"))
BASE_SCREEN_HEIGHT = int(os.getenv("BASE_SCREEN_HEIGHT", "1080"))
SCALE_COORDINATES = os.getenv("SCALE_COORDINATES", "true").strip().lower() in {"1", "true", "yes"}
FLIP_Y = os.getenv("FLIP_Y", "true").strip().lower() in {"1", "true", "yes"}

# Paths
BASE_DIR = Path(__file__).resolve().parent
LAST_ACTIONS_FILE = BASE_DIR / "last_actions.json"
SCREENSHOT_FILE = BASE_DIR / "screenshot.png"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOT_LOG_FILE = BASE_DIR / "screenshot_log.json"
FUNCTIONAL_TEST_LOG_FILE = BASE_DIR / "functional_test_log.json"
SCRIPTS_DIR = BASE_DIR / "scripts"