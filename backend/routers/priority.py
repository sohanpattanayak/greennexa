"""
backend/routers/priority.py — Priority alerts endpoints
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud
from backend.schemas.ai import PriorityAlertOut, AlertUpdateIn
from backend.services import priority as priority_svc

router = APIRouter(prefix="/priority", tags=["Priority Engine"])


@router.get("/alerts", response_model=list[PriorityAlertOut])
def get_priority_alerts(
    facility_id: int           = Query(...),
    status:      Optional[str] = Query(None),
    limit:       int           = Query(50),
    db: Session = Depends(get_db),
):
    return crud.get_priority_alerts(db, facility_id, status=status, limit=limit)


@router.post("/run")
def run_priority_engine(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """Re-compute priority scores for all open anomalies."""
    count = priority_svc.run_priority_engine(db, facility_id)
    return {"processed": count, "message": f"Priority engine ran — {count} alert(s) updated."}


@router.patch("/alerts/{alert_id}", response_model=PriorityAlertOut)
def update_alert(alert_id: int, payload: AlertUpdateIn, db: Session = Depends(get_db)):
    row = crud.update_priority_alert(
        db, alert_id,
        **{k: v for k, v in payload.model_dump().items() if v is not None}
    )
    if not row:
        raise HTTPException(404, "Alert not found.")
    return row
