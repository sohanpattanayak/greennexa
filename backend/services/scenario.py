"""
backend/services/scenario.py — What-If Scenario Simulation Service

Formula-based simulation — no external API, no ML training needed.
Impact coefficients are configurable per facility type.
"""

import json
import logging
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud
from backend.services.scorer import compute_sustainability_score

log = logging.getLogger("sfeid.scenario")
cfg = get_settings()

# ── Impact coefficients (configurable, calibrated for an engineering college) ──
COEFFICIENTS = {
    "energy_per_occupant_kwh":         0.08,    # kWh per additional occupant vs baseline
    "hvac_kwh_per_degree_per_1000sqft":0.40,    # kWh change per °C change per 1000 sqft
    "lighting_kwh_per_hour":           12.0,    # kWh per additional lighting hour (whole campus)
    "renewable_offset_factor":         0.95,    # fraction of renewable% that offsets grid draw
    "water_per_occupant_litres":       15.0,    # L per additional occupant per hour
    "recycling_save_factor":           0.70,    # fraction of water recycling that reduces demand
    "smart_scheduling_energy_saving":  0.08,    # 8% energy saving when enabled
}


def run_simulation(db: Session, params: dict) -> dict:
    """
    Run a what-if scenario and return impact deltas.
    params: ScenarioParams dict (from frontend)
    """
    facility_id = params["facility_id"]
    facility    = crud.get_facility(db, facility_id)
    if not facility:
        return {}

    area_sqft = float(facility.area_sqft or 850_000)

    # ── Baseline (7-day rolling averages) ─────────────────────────────────────
    def get_avg(metric: str, hours: int = 168) -> float:
        readings = crud.get_readings_last_n_hours(db, facility_id, metric, hours=hours)
        if not readings:
            return 0.0
        return float(np.mean([r.value for r in readings]))

    baseline_energy_kwh    = get_avg("energy_kwh",      hours=24)
    baseline_water_litres  = get_avg("water_litres",    hours=24)
    baseline_occupancy     = get_avg("occupancy_count", hours=24)

    # ── Scenario parameters ────────────────────────────────────────────────────
    occ_pct          = float(params.get("occupancy_pct",       80.0))
    hvac_setpoint    = float(params.get("hvac_setpoint_c",     24.0))
    lighting_hours   = float(params.get("lighting_hours",      12.0))
    renewable_pct    = float(params.get("renewable_pct",        0.0))
    recycling_pct    = float(params.get("water_recycling_pct",  0.0))
    waste_freq       = float(params.get("waste_freq_per_week",  3.0))
    smart_scheduling = bool(params.get("smart_scheduling",     False))

    max_capacity       = 5000.0
    scenario_occupancy = max_capacity * (occ_pct / 100.0)

    # Baseline HVAC setpoint assumed 24°C; baseline lighting assumed 12h/day
    BASELINE_HVAC_C      = 24.0
    BASELINE_LIGHTING_H  = 12.0
    BASELINE_RENEWABLE   = 0.0
    BASELINE_RECYCLING   = 0.0

    C = COEFFICIENTS

    # ── Energy delta ──────────────────────────────────────────────────────────
    occ_delta    = scenario_occupancy - baseline_occupancy
    energy_delta = (
        C["energy_per_occupant_kwh"] * occ_delta
        + C["hvac_kwh_per_degree_per_1000sqft"] * (hvac_setpoint - BASELINE_HVAC_C) * (area_sqft / 1000)
        + C["lighting_kwh_per_hour"] * (lighting_hours - BASELINE_LIGHTING_H)
        - C["renewable_offset_factor"] * ((renewable_pct - BASELINE_RENEWABLE) / 100) * baseline_energy_kwh
        - (C["smart_scheduling_energy_saving"] * baseline_energy_kwh if smart_scheduling else 0)
    )
    simulated_energy = max(0.0, baseline_energy_kwh + energy_delta)

    # ── Water delta ────────────────────────────────────────────────────────────
    water_delta = (
        C["water_per_occupant_litres"] * occ_delta
        - C["recycling_save_factor"] * ((recycling_pct - BASELINE_RECYCLING) / 100) * baseline_water_litres
    )
    simulated_water = max(0.0, baseline_water_litres + water_delta)

    # ── Cost deltas ────────────────────────────────────────────────────────────
    energy_cost_delta = energy_delta * cfg.electricity_tariff_inr_per_kwh
    water_cost_delta  = (water_delta / 1000) * cfg.water_tariff_inr_per_kl

    # ── CO₂ delta ──────────────────────────────────────────────────────────────
    # Only grid energy draws CO₂; renewable energy is zero-carbon
    grid_delta = energy_delta * (1.0 - renewable_pct / 100.0)
    co2_delta  = grid_delta * cfg.co2_kg_per_kwh

    # ── Sustainability score delta ─────────────────────────────────────────────
    # Re-use scoring formula with simulated values
    baseline_score = _quick_score(baseline_energy_kwh, baseline_water_litres, db, facility_id)
    scenario_score = _quick_score(simulated_energy,    simulated_water,        db, facility_id)
    score_delta    = scenario_score - baseline_score

    # ── Impact score (aggregate of improvements) ───────────────────────────────
    impact_score = float(np.clip(50 + score_delta * 2, 0, 100))

    result = {
        "name":                   params.get("name", "Unnamed Scenario"),
        "energy_delta_kwh":       round(energy_delta,       2),
        "energy_cost_delta_inr":  round(energy_cost_delta,  2),
        "water_delta_litres":     round(water_delta,        2),
        "water_cost_delta_inr":   round(water_cost_delta,   2),
        "co2_delta_kg":           round(co2_delta,          2),
        "score_delta":            round(score_delta,        1),
        "impact_score":           round(impact_score,       1),
        "baseline_summary": {
            "energy_kwh":       round(baseline_energy_kwh,   2),
            "water_litres":     round(baseline_water_litres, 2),
            "occupancy":        int(baseline_occupancy),
        },
        "simulated_summary": {
            "energy_kwh":       round(simulated_energy, 2),
            "water_litres":     round(simulated_water,  2),
            "occupancy":        int(scenario_occupancy),
        },
    }
    return result


def save_simulation(db: Session, facility_id: int, name: str, params: dict, result: dict):
    crud.create_simulation_run(
        db,
        facility_id=facility_id,
        name=name,
        parameters_json=json.dumps(params),
        results_json=json.dumps(result),
        impact_score=result.get("impact_score", 0),
    )


def _quick_score(energy_kwh: float, water_litres: float,
                  db: Session, facility_id: int) -> float:
    """Lightweight sustainability score estimate for scenario comparison."""
    facility   = crud.get_facility(db, facility_id)
    thresholds = {
        t.metric_type: t
        for t in crud.get_all_thresholds(db, facility.facility_type_id)
    }

    def _norm(val, crit_high):
        if not crit_high or crit_high == 0:
            return 0.5
        return max(0.0, min(1.0, 1.0 - val / crit_high))

    t_e = thresholds.get("energy_kwh")
    t_w = thresholds.get("water_litres")

    e_score = _norm(energy_kwh,   t_e.critical_high if t_e else 90)
    w_score = _norm(water_litres, t_w.critical_high if t_w else 1200)
    return (e_score * 0.5 + w_score * 0.5) * 100
