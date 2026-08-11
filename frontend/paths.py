import os
import platform
from pathlib import Path

if os.path.exists("/content") or platform.system() == "Linux":
    BASE_DIR = Path("/content")
else:
    BASE_DIR = Path.cwd() / "content"

DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
