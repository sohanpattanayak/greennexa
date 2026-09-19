"""
backend/services/rule_recommend.py — Rule-Based Recommendation Engine

Generates actionable recommendations from live sensor data and anomalies.
10+ rule templates covering all 5 metric categories.
No LLM required — fully deterministic.
"""

import json
import logging
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from backend.db import crud

log = logging.getLogger("sfeid.rule_recommend")

# ── Rule templates ─────────────────────────────────────────────────────────────
# Each rule: (category, priority_base, title_fn, description_fn, actions_list)

def _make_rules(stats: dict, anomaly_counts: dict) -> list[dict]:
    """
    stats: {metric_type: {"avg": float, "latest": float, "threshold_high": float, ...}}
    anomaly_counts: {metric_type: int}  — active (unresolved) anomalies per metric
    """
    rules = []

    # ── Energy rules ──────────────────────────────────────────────────────────
    e = stats.get("energy_kwh", {})
    if e:
        avg = e.get("avg", 0)
        high = e.get("threshold_high", 70)
        pct_over = max(0, (avg - high) / high * 100) if high else 0

        if pct_over > 20:
            rules.append({
                "category":       "energy",
                "priority_score": min(95, 70 + pct_over),
                "title":          "High Energy Consumption — Immediate Action Required",
                "description":    f"Average energy draw ({avg:.1f} kWh) is {pct_over:.0f}% above the recommended threshold ({high} kWh). This significantly increases operational costs and carbon footprint.",
                "action_items":   [
                    "Audit HVAC scheduling — consider reducing setpoint by 2°C during off-peak hours.",
                    "Identify and shut down idle lab equipment and lighting in unoccupied zones.",
                    "Check for HVAC or equipment faults that may cause excess draw.",
                    "Review energy usage patterns in the Priority Engine for zone-level insights.",
                ],
            })
        elif pct_over > 5:
            rules.append({
                "category":       "energy",
                "priority_score": 55 + pct_over,
                "title":          "Energy Consumption Above Target",
                "description":    f"Energy usage ({avg:.1f} kWh) is moderately above the target ({high} kWh). Small adjustments can improve sustainability score.",
                "action_items":   [
                    "Switch off lights in unoccupied classrooms and corridors.",
                    "Adjust HVAC setpoint by 1°C during lunch break.",
                    "Encourage staff to turn off personal devices when leaving.",
                ],
            })
        elif anomaly_counts.get("energy_kwh", 0) == 0 and avg < high * 0.7:
            rules.append({
                "category":       "energy",
                "priority_score": 30,
                "title":          "Energy Consumption is Efficient — Maintain Practices",
                "description":    f"Current energy usage ({avg:.1f} kWh) is well below threshold. Current practices are effective.",
                "action_items":   [
                    "Document current scheduling practices as a template for other facilities.",
                    "Consider shifting more lab activities to low-tariff hours.",
                ],
            })

    # ── Air Quality rules ──────────────────────────────────────────────────────
    pm25_s = stats.get("pm25", {})
    if pm25_s:
        pm25_avg = pm25_s.get("avg", 0)
        pm25_high = pm25_s.get("threshold_high", 35)
        if pm25_avg > pm25_high:
            rules.append({
                "category":       "air",
                "priority_score": min(90, 60 + (pm25_avg - pm25_high) * 1.5),
                "title":          f"Poor Air Quality — PM2.5 at {pm25_avg:.1f} µg/m³",
                "description":    f"PM2.5 levels ({pm25_avg:.1f} µg/m³) exceed the warning threshold ({pm25_high} µg/m³). Prolonged exposure may affect student and staff health.",
                "action_items":   [
                    "Increase fresh-air ventilation in affected zones.",
                    "Check if HVAC filters need replacement (recommend quarterly for college campuses).",
                    "Temporarily restrict parking/vehicle idling near air quality sensors.",
                    "Alert facilities management to inspect nearby construction or burning activity.",
                ],
            })

    # ── Water rules ───────────────────────────────────────────────────────────
    w = stats.get("water_litres", {})
    if w:
        w_avg  = w.get("avg", 0)
        w_high = w.get("threshold_high", 800)
        if w_avg > w_high * 1.15:
            rules.append({
                "category":       "water",
                "priority_score": 65,
                "title":          "Above-Normal Water Consumption Detected",
                "description":    f"Hourly water usage ({w_avg:.0f} L) is significantly above the expected level ({w_high} L). This may indicate a leak or open tap.",
                "action_items":   [
                    "Inspect canteen plumbing and hostel water fixtures for leaks.",
                    "Check toilet flush systems in high-usage zones.",
                    "Consider installing flow restrictors in non-critical taps.",
                    "Review water meter logs in MySQL to identify the spike time.",
                ],
            })

    # ── Waste rules ────────────────────────────────────────────────────────────
    b = stats.get("bin_fill_pct", {})
    if b:
        fill = b.get("latest", 0)
        if fill >= 90:
            rules.append({
                "category":       "waste",
                "priority_score": 88,
                "title":          f"Waste Bin Critical — {fill:.0f}% Full",
                "description":    "One or more waste bins are at or near capacity. Overflow risk is high and poses hygiene and compliance risks.",
                "action_items":   [
                    "Dispatch housekeeping staff for immediate bin collection.",
                    "Increase collection frequency for high-traffic zones (canteen, corridors).",
                    "Review whether bin capacity is sufficient for peak-hour usage.",
                ],
            })
        elif fill >= 75:
            rules.append({
                "category":       "waste",
                "priority_score": 60,
                "title":          f"Waste Bin Filling — Schedule Collection Soon ({fill:.0f}%)",
                "description":    "Bin fill level has reached the warning threshold. Schedule collection before the next peak period.",
                "action_items":   [
                    "Schedule housekeeping collection in the next hour.",
                    "Check if peak-hour waste generation can be managed with additional bins.",
                ],
            })

    # ── Temperature / Comfort rules ────────────────────────────────────────────
    t = stats.get("temperature_c", {})
    if t:
        t_avg  = t.get("avg", 0)
        t_high = t.get("threshold_high", 32)
        t_low  = t.get("threshold_low", 16)
        if t_avg > t_high:
            rules.append({
                "category":       "energy",
                "priority_score": 72,
                "title":          f"High Temperature Alert — {t_avg:.1f}°C",
                "description":    f"Average temperature ({t_avg:.1f}°C) exceeds the comfort threshold ({t_high}°C). This may affect productivity and indicate HVAC inefficiency.",
                "action_items":   [
                    "Lower HVAC setpoint by 2°C in affected zones.",
                    "Check HVAC unit operation and refrigerant levels.",
                    "Open windows where possible to allow natural ventilation.",
                ],
            })
        elif t_avg < t_low:
            rules.append({
                "category":       "energy",
                "priority_score": 50,
                "title":          f"Low Temperature Alert — {t_avg:.1f}°C",
                "description":    f"Temperature ({t_avg:.1f}°C) is below the comfort threshold ({t_low}°C). Heating may be needed.",
                "action_items":   [
                    "Raise HVAC setpoint by 2°C.",
                    "Verify HVAC heating mode is active.",
                ],
            })

    # ── Occupancy / Space utilisation rules ────────────────────────────────────
    oc = stats.get("occupancy_count", {})
    if oc:
        occ = oc.get("avg", 0)
        max_cap = oc.get("threshold_high", 4500)
        if occ > max_cap:
            rules.append({
                "category":       "occupancy",
                "priority_score": 80,
                "title":          f"Overcrowding Risk — {int(occ):,} occupants detected",
                "description":    f"Current occupancy ({int(occ):,}) exceeds the recommended maximum ({int(max_cap):,}). This may pose safety and comfort risks.",
                "action_items":   [
                    "Stagger class schedules to distribute load across the day.",
                    "Open additional zones (seminar halls, outdoor spaces) for use.",
                    "Alert security and facilities management.",
                ],
            })
        elif occ < max_cap * 0.20:
            rules.append({
                "category":       "occupancy",
                "priority_score": 25,
                "title":          "Low Campus Occupancy — Opportunity to Reduce Consumption",
                "description":    f"Occupancy is low ({int(occ):,} people). This is an opportunity to reduce energy and water use.",
                "action_items":   [
                    "Switch off HVAC and lighting in unoccupied zones.",
                    "Consolidate classes into fewer buildings to reduce zone heating/cooling.",
                ],
            })

    # ── Equipment utilisation rule ─────────────────────────────────────────────
    eu = stats.get("equipment_util_pct", {})
    if eu:
        util = eu.get("avg", 0)
        if util > 90:
            rules.append({
                "category":       "occupancy",
                "priority_score": 55,
                "title":          f"Lab Equipment Near Capacity — {util:.0f}% Utilisation",
                "description":    "Lab equipment is heavily used. High utilisation over extended periods may accelerate wear and increase energy consumption.",
                "action_items":   [
                    "Review lab scheduling to ensure equipment has cooldown periods.",
                    "Check if equipment maintenance is due.",
                    "Consider adding equipment to accommodate demand.",
                ],
            })

    return rules


def generate_recommendations(db: Session, facility_id: int) -> int:
    """
    Run rule engine and persist recommendations.
    Returns count of recommendations generated.
    """
    from backend.db.models import Recommendation

    # Gather stats
    stats = {}
    METRICS = ["energy_kwh", "pm25", "pm10", "water_litres", "bin_fill_pct",
               "temperature_c", "humidity_pct", "occupancy_count", "equipment_util_pct"]

    facility = crud.get_facility(db, facility_id)
    if not facility:
        return 0

    thresholds = {
        t.metric_type: t
        for t in crud.get_all_thresholds(db, facility.facility_type_id)
    }

    import numpy as np
    for mt in METRICS:
        readings = crud.get_readings_last_n_hours(db, facility_id, mt, hours=6)
        if readings:
            vals = [r.value for r in readings]
            t = thresholds.get(mt)
            stats[mt] = {
                "avg":             float(np.mean(vals)),
                "latest":          float(readings[-1].value),
                "threshold_high":  t.warn_high if t else None,
                "threshold_low":   t.warn_low  if t else None,
                "threshold_crit":  t.critical_high if t else None,
            }

    anomaly_counts = {
        mt: len(crud.get_anomalies(db, facility_id, resolved=False, limit=50))
        for mt in METRICS
    }

    rules = _make_rules(stats, anomaly_counts)

    # Clear old unacknowledged rule_engine recommendations
    db.query(Recommendation).filter(
        Recommendation.facility_id    == facility_id,
        Recommendation.source         == "rule_engine",
        Recommendation.is_acknowledged == False,
    ).delete()
    db.commit()

    # Insert new ones
    for rule in rules:
        rec = Recommendation(
            facility_id=facility_id,
            category=rule["category"],
            priority_score=float(rule["priority_score"]),
            title=rule["title"],
            description=rule["description"],
            action_items_json=json.dumps(rule["action_items"]),
            source="rule_engine",
            generated_at=datetime.utcnow(),
        )
        db.add(rec)

    db.commit()
    log.info(f"Generated {len(rules)} recommendations for facility {facility_id}")
    return len(rules)
