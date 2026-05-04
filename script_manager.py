from pathlib import Path
from typing import List

from config import SCRIPTS_DIR


def get_script_files() -> List[Path]:
    if not SCRIPTS_DIR.exists() or not SCRIPTS_DIR.is_dir():
        return []
    return sorted([path for path in SCRIPTS_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".txt"])


def load_script_text(script_path: Path) -> str:
    try:
        return script_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""