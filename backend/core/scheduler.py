"""
backend/core/scheduler.py — APScheduler jobs
  - Synthetic data generator (every N seconds)
  - Nightly ML model retraining (placeholder — Day 2)
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler

from backend.core.config import get_settings
from backend.db.database import SessionLocal
from backend.db import crud
from backend.services import synthetic as syn_svc

log      = settings = None   # lazy init
_scheduler: BackgroundScheduler | None = None
_synthetic_running = False


def _run_synthetic_job():
    """Insert one round of synthetic readings for the default facility."""
    try:
        db = SessionLocal()
        cfg = get_settings()
        sensors = crud.get_sensors(db, cfg.default_facility_id)
        rows    = syn_svc.generate_all_readings(sensors, cfg.default_facility_id)
        if rows:
            crud.bulk_create_readings(db, rows)
        db.close()
    except Exception as exc:
        logging.getLogger("sfeid.scheduler").warning(f"Synthetic job error: {exc}")


def start_scheduler():
    global _scheduler, _synthetic_running
    cfg = get_settings()
    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    if cfg.synthetic_enabled:
        _scheduler.add_job(
            _run_synthetic_job,
            trigger="interval",
            seconds=cfg.synthetic_interval_seconds,
            id="synthetic_feed",
            replace_existing=True,
        )
        _synthetic_running = True
        logging.getLogger("sfeid.scheduler").info(
            f"Synthetic generator started — every {cfg.synthetic_interval_seconds}s"
        )

    _scheduler.start()


def stop_scheduler():
    global _scheduler, _synthetic_running
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _synthetic_running = False


def toggle_synthetic(enable: bool) -> bool:
    global _synthetic_running
    cfg = get_settings()
    if _scheduler is None:
        return False
    if enable and not _synthetic_running:
        _scheduler.add_job(
            _run_synthetic_job,
            trigger="interval",
            seconds=cfg.synthetic_interval_seconds,
            id="synthetic_feed",
            replace_existing=True,
        )
        _synthetic_running = True
    elif not enable and _synthetic_running:
        _scheduler.remove_job("synthetic_feed")
        _synthetic_running = False
    return _synthetic_running


def synthetic_status() -> dict:
    return {
        "running":           _synthetic_running,
        "interval_seconds":  get_settings().synthetic_interval_seconds,
    }
