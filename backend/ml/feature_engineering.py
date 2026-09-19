"""
backend/ml/feature_engineering.py — Shared time-series feature builders
Used by both anomaly detection and forecasting services.
"""

import numpy as np
import pandas as pd


ALL_METRICS = [
    "energy_kwh", "pm25", "pm10", "water_litres",
    "bin_fill_pct", "temperature_c", "humidity_pct",
    "occupancy_count", "parking_count", "equipment_util_pct",
]

# India public holidays (approximate, configurable)
INDIA_HOLIDAYS = {
    (1, 26): "Republic Day",
    (8, 15): "Independence Day",
    (10, 2): "Gandhi Jayanti",
}


def readings_to_dataframe(readings: list) -> pd.DataFrame:
    """
    Convert list of SensorReading ORM objects or dicts to a clean DataFrame.
    Columns: timestamp (datetime), value (float)
    """
    if not readings:
        return pd.DataFrame(columns=["timestamp", "value"])

    rows = []
    for r in readings:
        if isinstance(r, dict):
            rows.append({"timestamp": r["timestamp"], "value": float(r["value"])})
        else:
            rows.append({"timestamp": r.timestamp, "value": float(r.value)})

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.drop_duplicates(subset="timestamp")
    return df


def add_time_features(df: pd.DataFrame, ts_col: str = "timestamp") -> pd.DataFrame:
    """
    Add time-based features to a DataFrame.
    Required for sklearn models (anomaly + fallback forecast).
    """
    df = df.copy()
    dt = df[ts_col]

    df["hour_of_day"]    = dt.dt.hour
    df["day_of_week"]    = dt.dt.dayofweek          # 0=Mon … 6=Sun
    df["is_weekend"]     = (dt.dt.dayofweek >= 5).astype(int)
    df["month"]          = dt.dt.month
    df["hour_sin"]       = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"]       = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    df["day_sin"]        = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"]        = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["is_holiday"]     = df[ts_col].apply(
        lambda t: int((t.month, t.day) in INDIA_HOLIDAYS)
    )
    return df


def add_rolling_features(df: pd.DataFrame, value_col: str = "value",
                          windows_h: list[int] = None) -> pd.DataFrame:
    """Add rolling mean and std features (using time-based windows)."""
    if windows_h is None:
        windows_h = [3, 24]   # 3-hour and 24-hour

    df = df.set_index("timestamp").copy()

    for w in windows_h:
        window_str = f"{w}h"
        df[f"rolling_{w}h_mean"] = (
            df[value_col].rolling(window=window_str, min_periods=1).mean()
        )
        df[f"rolling_{w}h_std"]  = (
            df[value_col].rolling(window=window_str, min_periods=2).std().fillna(0)
        )

    return df.reset_index()


def build_feature_matrix(df: pd.DataFrame,
                          value_col: str = "value") -> tuple[np.ndarray, list[str]]:
    """
    Build the feature matrix X used for Isolation Forest and fallback LinearRegression.
    Returns (X_array, feature_names).
    """
    df = add_time_features(df)
    df = add_rolling_features(df, value_col=value_col)

    feature_cols = [
        value_col,
        "hour_sin", "hour_cos",
        "day_sin",  "day_cos",
        "is_weekend", "is_holiday",
        "rolling_3h_mean", "rolling_3h_std",
        "rolling_24h_mean",
    ]
    # Only keep cols that exist (rolling cols may be missing for tiny datasets)
    feature_cols = [c for c in feature_cols if c in df.columns]

    X = df[feature_cols].fillna(0).values
    return X, feature_cols


def prepare_prophet_df(df: pd.DataFrame,
                        value_col: str = "value") -> pd.DataFrame:
    """
    Convert a DataFrame to Prophet's expected format: columns ['ds', 'y'].
    Resamples to hourly frequency (taking the mean within each hour).
    """
    df = df.set_index("timestamp")
    df_hourly = df[[value_col]].resample("1h").mean().dropna()
    df_hourly = df_hourly.reset_index()
    df_hourly.columns = ["ds", "y"]
    df_hourly["ds"] = pd.to_datetime(df_hourly["ds"])
    return df_hourly
