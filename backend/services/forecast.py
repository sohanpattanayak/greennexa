"""
backend/services/forecast.py — Time-Series Forecasting Service

Primary:  Prophet (Meta) — requires ≥ 100 rows
Fallback: sklearn LinearRegression — used when insufficient data
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud
from backend.ml.feature_engineering import (
    readings_to_dataframe, add_time_features, prepare_prophet_df
)

log = logging.getLogger("sfeid.forecast")
cfg = get_settings()

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

FORECAST_FRESHNESS_HOURS = 1   # re-use stored forecast if < 1h old


# ── Public entry point ────────────────────────────────────────────────────────

def get_or_generate_forecast(db: Session, facility_id: int,
                             metric_type: str) -> Optional[dict]:
    """
    Returns a stored forecast if fresh (< 1h old), otherwise generates a new one.
    """
    stored = crud.get_latest_forecast(db, facility_id, metric_type)
    if stored:
        age = (datetime.utcnow() - stored.generated_at).total_seconds() / 3600
        if age < FORECAST_FRESHNESS_HOURS:
            return json.loads(stored.forecast_json)

    return generate_forecast(db, facility_id, metric_type)


def generate_forecast(db: Session, facility_id: int,
                      metric_type: str, horizon_hours: int = 24) -> Optional[dict]:
    """
    Generate a 24-hour forecast for a metric. Uses Prophet if enough data,
    otherwise falls back to LinearRegression.
    """
    readings = crud.get_readings_last_n_days(db, facility_id, metric_type, days=30)

    if len(readings) < 10:
        log.info(f"Insufficient data for forecast: {metric_type} (only {len(readings)} rows)")
        return None

    if len(readings) >= cfg.min_rows_for_prophet:
        result = _forecast_prophet(readings, horizon_hours)
        model_used = "prophet"
    else:
        result = _forecast_linear(readings, horizon_hours)
        model_used = "linear_regression_fallback"

    if result is None:
        return None

    payload = {
        "facility_id":   facility_id,
        "metric_type":   metric_type,
        "model_used":    model_used,
        "generated_at":  datetime.utcnow().isoformat(),
        "horizon_hours": horizon_hours,
        "points":        result,
    }

    crud.upsert_forecast(
        db,
        facility_id=facility_id,
        metric_type=metric_type,
        forecast_json=json.dumps(payload),
        model_used=model_used,
        horizon_hours=horizon_hours,
    )

    return payload


# ── Prophet ───────────────────────────────────────────────────────────────────

def _forecast_prophet(readings: list, horizon_hours: int) -> Optional[list]:
    try:
        from prophet import Prophet   # import here so app boots without prophet if needed
    except ImportError:
        log.warning("Prophet not installed — falling back to LinearRegression.")
        return _forecast_linear(readings, horizon_hours)

    try:
        df_raw   = readings_to_dataframe(readings)
        df_prophet = prepare_prophet_df(df_raw)

        if len(df_prophet) < cfg.min_rows_for_prophet:
            log.info(f"After hourly resampling only {len(df_prophet)} rows — using LinearRegression.")
            return _forecast_linear(readings, horizon_hours)

        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,  # not enough data for yearly
            uncertainty_samples=200,
        )
        model.add_country_holidays(country_name="IN")
        model.fit(df_prophet)

        future   = model.make_future_dataframe(periods=horizon_hours, freq="h")
        forecast  = model.predict(future)

        # Keep only future rows (beyond last observed timestamp)
        last_ts  = df_prophet["ds"].max()
        fcast    = forecast[forecast["ds"] > last_ts].copy()

        points = []
        for _, row in fcast.head(horizon_hours).iterrows():
            points.append({
                "timestamp":  row["ds"].isoformat(),
                "yhat":       round(float(row["yhat"]),       2),
                "yhat_lower": round(float(row["yhat_lower"]), 2),
                "yhat_upper": round(float(row["yhat_upper"]), 2),
            })
        return points

    except Exception as exc:
        log.warning(f"Prophet forecast failed: {exc}")
        return _forecast_linear(readings, horizon_hours)


# ── Linear Regression fallback ────────────────────────────────────────────────

def _forecast_linear(readings: list, horizon_hours: int) -> Optional[list]:
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import StandardScaler

        df = readings_to_dataframe(readings)
        if len(df) < 10:
            return None

        df = add_time_features(df)

        feature_cols = ["hour_sin", "hour_cos", "day_sin", "day_cos", "is_weekend", "is_holiday"]

        X = df[feature_cols].values
        y = df["value"].values

        scaler = StandardScaler()
        X_s    = scaler.fit_transform(X)

        model = LinearRegression()
        model.fit(X_s, y)

        # Residual std for approximate confidence interval
        y_pred  = model.predict(X_s)
        resid   = y - y_pred
        resid_std = float(resid.std())

        # Generate future timestamps
        last_ts = df["timestamp"].max()
        future_df = pd.DataFrame({
            "timestamp": [last_ts + timedelta(hours=i+1) for i in range(horizon_hours)]
        })
        future_df = add_time_features(future_df)
        Xf = future_df[feature_cols].values
        Xf_s = scaler.transform(Xf)

        y_fut = model.predict(Xf_s)

        points = []
        for i, (ts, yh) in enumerate(zip(future_df["timestamp"], y_fut)):
            yh = max(0.0, float(yh))
            points.append({
                "timestamp":  ts.isoformat(),
                "yhat":       round(yh, 2),
                "yhat_lower": round(max(0.0, yh - 1.96 * resid_std), 2),
                "yhat_upper": round(yh + 1.96 * resid_std, 2),
            })
        return points

    except Exception as exc:
        log.warning(f"LinearRegression forecast failed: {exc}")
        return None
