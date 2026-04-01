from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import discovery, workflows
from app.db.init_db import ensure_db_initialized


ensure_db_initialized()
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Data Gather Agent", version="0.1.0")
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
