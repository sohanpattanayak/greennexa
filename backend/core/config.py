"""
backend/core/config.py — Application Settings
Loaded from .env via Pydantic BaseSettings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Database ──────────────────────────────────────────────
    db_host: str     = "localhost"
    db_port: int     = 3306
    db_user: str     = "root"
    db_password: str = ""
    db_name: str     = "sfeid_db"

    # ── FastAPI ───────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Frontend ──────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"

    # ── Auth (simple password gate) ───────────────────────────
    admin_password: str = "sfeid2026"

    # ── Synthetic generator ───────────────────────────────────
    synthetic_enabled: bool = True
    synthetic_interval_seconds: int = 60

    # ── Gemini (optional LLM) ─────────────────────────────────
    gemini_api_key: str = ""

    # ── Default facility ─────────────────────────────────────
    default_facility_id: int = 1

    # ── Tariff / cost config ──────────────────────────────────
    electricity_tariff_inr_per_kwh: float = 8.0
    water_tariff_inr_per_kl: float        = 15.0
    co2_kg_per_kwh: float                 = 0.82

    # ── ML config ────────────────────────────────────────────
    isolation_forest_contamination: float = 0.05
    anomaly_zscore_threshold: float       = 3.0
    min_rows_for_isolation_forest: int    = 500
    min_rows_for_prophet: int             = 100

    # ── Priority Engine weights ───────────────────────────────
    priority_w_severity:   float = 0.40
    priority_w_trend:      float = 0.20
    priority_w_impact:     float = 0.20
    priority_w_time:       float = 0.10
    priority_w_recurrence: float = 0.10

    # ── Sustainability score weights ──────────────────────────
    score_w_energy:    float = 0.30
    score_w_water:     float = 0.20
    score_w_waste:     float = 0.15
    score_w_air:       float = 0.20
    score_w_occupancy: float = 0.15

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
