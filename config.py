import os
from pathlib import Path

# Local Ollama configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Paths
BASE_DIR = Path(__file__).resolve().parent
LAST_ACTIONS_FILE = BASE_DIR / "last_actions.json"
SCREENSHOT_FILE = BASE_DIR / "screenshot.png"
SCRIPTS_DIR = BASE_DIR / "scripts"