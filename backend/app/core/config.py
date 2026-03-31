import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _default_db_path() -> Path:
    configured = os.getenv("DATA_GATHER_DB_PATH")
    if configured:
        return Path(configured)
    if os.name == "nt":
        fallback_dir = Path.home() / ".codex" / "memories"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "data-gather-agent.sqlite3"
    return DATA_DIR / "workflow.sqlite3"


DB_PATH = _default_db_path()
