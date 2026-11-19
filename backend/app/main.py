"""FastAPI entry point: `uvicorn app.main:app --reload` from backend/."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit_log, comparisons, inspections, knowledge, walls
from app.config import get_settings
from app.database.session import init_engine
from app.vision.detectors import get_detector


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_engine()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Heritage Conservation Copilot",
        description="وكيل ذكي لدعم قرارات ترميم التراث الطيني (نموذج أولي). الوكيل يقترح، والمختص يقرر.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (walls.router, inspections.router, comparisons.router, knowledge.router, audit_log.router):
        app.include_router(r)

    @app.get("/api/health")
    def health():
        info = get_detector().info
        return {
            "status": "ok",
            "detector": info.__dict__,
            "original_images_stored": False,
            "privacy_notice_ar": "تُخفى الوجوه آليًا قبل التحليل والتخزين. لا يُستخدم النظام لتتبع الأشخاص أو تحليل سلوك الزوار.",
        }

    return app


app = create_app()
