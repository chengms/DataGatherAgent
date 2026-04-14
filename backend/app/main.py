from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import discovery, external_exports, workflows
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.db.init_db import ensure_db_initialized
from app.middleware.error_handler import (
    app_exception_handler,
    general_exception_handler,
    validation_exception_handler,
)

configure_logging()
ensure_db_initialized()
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Data Gather Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4000",
        "http://localhost:4010",
        "http://127.0.0.1:4000",
        "http://127.0.0.1:4010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(external_exports.router, prefix="/api/external/v1", tags=["external"])
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index_v2.html")
