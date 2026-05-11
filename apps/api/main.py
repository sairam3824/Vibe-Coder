"""FastAPI entrypoint for Vibe Coder."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.db.base import Base
from apps.api.db.migrations import migrate_database
from apps.api.db.session import engine
from apps.api.routes.health import router as health_router
from apps.api.routes.meta import router as meta_router
from apps.api.routes.runs import router as runs_router
from apps.api.services.logging import configure_logging


configure_logging()
settings = get_settings()
Base.metadata.create_all(bind=engine)
migrate_database(engine)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(meta_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
