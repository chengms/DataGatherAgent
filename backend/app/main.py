from fastapi import FastAPI

from app.api.routes import discovery, workflows
from app.db.init_db import ensure_db_initialized


ensure_db_initialized()

app = FastAPI(title="Data Gather Agent", version="0.1.0")
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
