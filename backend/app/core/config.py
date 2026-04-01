import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXTERNAL_TOOLS_DIR = BASE_DIR / "external_tools"
EXTERNAL_TOOLS_DIR.mkdir(parents=True, exist_ok=True)


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


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in {"", None} else default


WECHAT_EXPORTER_BASE_URL = get_env("WECHAT_EXPORTER_BASE_URL", "https://down.mptext.top")
WECHAT_EXPORTER_API_KEY = get_env("WECHAT_EXPORTER_API_KEY")
XHS_MEDIACRAWLER_BASE_URL = get_env("XHS_MEDIACRAWLER_BASE_URL", "http://127.0.0.1:8080")
