"""
backend/routers/scores.py — Sustainability score endpoints
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud
from backend.services import scorer as scorer_svc

router = APIRouter(prefix="/scores", tags=["Scores"])


@router.get("/sustainability")
def get_score(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """Return today's sustainability score, computing it if not yet done."""
    from datetime import date
    stored = (
        db.query(crud.models.SustainabilityScore)
        .filter(
            crud.models.SustainabilityScore.facility_id == facility_id,
            crud.models.SustainabilityScore.score_date  == date.today(),
        )
        .first()
    )
    if stored:
        return {
            "facility_id":    stored.facility_id,
            "score_date":     stored.score_date.isoformat(),
            "overall_score":  stored.overall_score,
            "energy_score":   stored.energy_score,
            "water_score":    stored.water_score,
            "waste_score":    stored.waste_score,
            "air_score":      stored.air_score,
            "occupancy_score":stored.occupancy_score,
            "grade":          _grade(stored.overall_score),
        }
    return scorer_svc.compute_sustainability_score(db, facility_id)


@router.get("/history")
def score_history(
    facility_id: int = Query(...),
    days:        int = Query(30),
    db: Session = Depends(get_db),
):
    rows = crud.get_score_history(db, facility_id, days=days)
    return [
        {
            "score_date":     r.score_date.isoformat(),
            "overall_score":  r.overall_score,
            "energy_score":   r.energy_score,
            "water_score":    r.water_score,
            "waste_score":    r.waste_score,
            "air_score":      r.air_score,
            "occupancy_score":r.occupancy_score,
        }
        for r in rows
    ]


@router.post("/compute")
def compute_score(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """Force recompute today's score."""
    return scorer_svc.compute_sustainability_score(db, facility_id)


def _grade(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"
