"""
backend/routers/ai.py — AI recommendations, chat, voice, scenario endpoints
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud
from backend.schemas.ai import (
    RecommendationOut, ChatMessageIn, ChatResponse, AIStatusResponse,
    ScenarioParams, ScenarioResult,
)
from backend.core.config import get_settings
from backend.services import rule_recommend, voice_chat as vc_svc

router = APIRouter(prefix="/ai", tags=["AI & Chat"])
cfg    = get_settings()


@router.get("/status", response_model=AIStatusResponse)
def ai_status():
    enabled = cfg.llm_enabled
    return AIStatusResponse(
        llm_enabled=enabled,
        mode="LLM-enhanced (Gemini)" if enabled else "Rule-based (offline)",
    )


# ── Recommendations ────────────────────────────────────────────────────────────

@router.post("/recommendations/generate")
def generate_recommendations(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """Run rule engine (+ optional LLM) and persist recommendations."""
    count = rule_recommend.generate_recommendations(db, facility_id)

    # If LLM enabled, optionally enhance with Gemini
    if cfg.llm_enabled:
        try:
            from backend.services.gemini_svc import generate_llm_recommendations
            from backend.db.models import Recommendation
            snapshot = vc_svc.get_context_snapshot(db, facility_id)
            llm_recs = generate_llm_recommendations(snapshot["live"])
            for r in llm_recs:
                import json
                rec = Recommendation(
                    facility_id=facility_id,
                    category=r.get("category", "general"),
                    priority_score=60.0,
                    title=r.get("title", "AI Recommendation"),
                    description=r.get("description", ""),
                    action_items_json=json.dumps(r.get("action_items", [])),
                    source="llm",
                )
                db.add(rec)
            db.commit()
            count += len(llm_recs)
        except Exception:
            pass

    return {"generated": count, "message": f"{count} recommendations generated."}


@router.get("/recommendations/", response_model=list[RecommendationOut])
def list_recommendations(
    facility_id:  int  = Query(...),
    acknowledged: bool = Query(False),
    limit:        int  = Query(20),
    db: Session = Depends(get_db),
):
    return crud.get_recommendations(db, facility_id, acknowledged=acknowledged, limit=limit)


@router.patch("/recommendations/{rec_id}/acknowledge")
def acknowledge_recommendation(rec_id: int, db: Session = Depends(get_db)):
    row = crud.acknowledge_recommendation(db, rec_id)
    if not row:
        raise HTTPException(404, "Recommendation not found.")
    return {"acknowledged": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatMessageIn, db: Session = Depends(get_db)):
    result = vc_svc.process_chat(db, payload.facility_id, payload.message)
    return ChatResponse(**result)


@router.post("/voice", response_model=ChatResponse)
async def voice_chat(
    facility_id: int        = Query(...),
    audio_file:  UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a WAV/MP3 file → transcribe → chat response."""
    audio_bytes = await audio_file.read()
    transcript  = vc_svc.transcribe_audio(audio_bytes)

    if not transcript:
        raise HTTPException(
            422,
            "Could not transcribe audio. Please check the file format (WAV/MP3 recommended) "
            "or use text input instead."
        )

    result = vc_svc.process_chat(db, facility_id, transcript)
    return ChatResponse(**result)


@router.get("/chat/history")
def chat_history(
    facility_id: int = Query(...),
    limit:       int = Query(50),
    db: Session = Depends(get_db),
):
    rows = crud.get_chat_history(db, facility_id, limit=limit)
    return [{"role": r.role, "message": r.message,
             "source": r.source, "created_at": r.created_at} for r in rows]


# ── Scenario ──────────────────────────────────────────────────────────────────

scenario_router = APIRouter(prefix="/scenario", tags=["Scenario Simulation"])


@scenario_router.post("/simulate")
def simulate(params: ScenarioParams, db: Session = Depends(get_db)):
    from backend.services import scenario as scenario_svc
    result = scenario_svc.run_simulation(db, params.model_dump())
    if not result:
        raise HTTPException(404, "Facility not found.")
    return result


@scenario_router.post("/simulate/save")
def simulate_and_save(params: ScenarioParams, db: Session = Depends(get_db)):
    from backend.services import scenario as scenario_svc
    result = scenario_svc.run_simulation(db, params.model_dump())
    if not result:
        raise HTTPException(404, "Facility not found.")
    scenario_svc.save_simulation(
        db, params.facility_id, params.name, params.model_dump(), result
    )
    return result


@scenario_router.get("/runs")
def list_simulation_runs(
    facility_id: int = Query(...),
    limit:       int = Query(20),
    db: Session = Depends(get_db),
):
    rows = crud.get_simulation_runs(db, facility_id, limit=limit)
    import json
    return [
        {
            "id":         r.id,
            "name":       r.name,
            "created_at": r.created_at,
            "impact_score": r.impact_score,
            "results":    json.loads(r.results_json),
        }
        for r in rows
    ]


@scenario_router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: int, db: Session = Depends(get_db)):
    from backend.db.models import SimulationRun
    row = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if row:
        db.delete(row)
        db.commit()
