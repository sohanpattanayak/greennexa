"""
backend/main.py — FastAPI application entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.core import scheduler
from backend.routers.ingest     import router as ingest_router
from backend.routers.sensors    import router as sensors_router, readings_router
from backend.routers.admin      import router as admin_router
from backend.routers.analytics  import router as analytics_router
from backend.routers.priority   import router as priority_router
from backend.routers.scores     import router as scores_router
from backend.routers.ai         import router as ai_router, scenario_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("sfeid.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    cfg = get_settings()
    log.info("SFEID Backend starting up…")
    log.info(f"LLM mode: {'enabled (Gemini)' if cfg.llm_enabled else 'rule-based (offline)'}")
    scheduler.start_scheduler()

    yield   # ← application runs here

    # ── Shutdown ─────────────────────────────────────────
    log.info("SFEID Backend shutting down…")
    scheduler.stop_scheduler()


app = FastAPI(
    title="SFEID — Sustainable Facility & Estate Intelligence Dashboard",
    description=(
        "Backend API for the SFEID hackathon project. "
        "Handles sensor ingestion, analytics, ML, AI recommendations, "
        "priority engine, scenario simulation, and admin functions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow Streamlit frontend (localhost:8501) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── All routers ──────────────────────────────────────────────────────────────
app.include_router(ingest_router)
app.include_router(sensors_router)
app.include_router(readings_router)
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(priority_router)
app.include_router(scores_router)
app.include_router(ai_router)
app.include_router(scenario_router)


@app.get("/", tags=["Health"])
def root():
    cfg = get_settings()
    return {
        "status":      "ok",
        "project":     "SFEID",
        "llm_enabled": cfg.llm_enabled,
        "docs":        "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
