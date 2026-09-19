"""
backend/schemas/ai.py — Pydantic schemas for AI, priority, and scenario endpoints
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationOut(BaseModel):
    id:               int
    facility_id:      int
    category:         str
    priority_score:   float
    title:            str
    description:      Optional[str]
    action_items_json:Optional[str]
    source:           str
    generated_at:     datetime
    is_acknowledged:  bool

    model_config = {"from_attributes": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    facility_id: int
    message:     str


class ChatResponse(BaseModel):
    reply:   str
    source:  str   # rule_engine | llm
    intent:  str


class AIStatusResponse(BaseModel):
    llm_enabled:    bool
    mode:           str   # "LLM-enhanced (Gemini)" | "Rule-based (offline)"


# ── Priority ──────────────────────────────────────────────────────────────────

class PriorityAlertOut(BaseModel):
    id:             int
    facility_id:    int
    anomaly_id:     Optional[int]
    title:          str
    description:    Optional[str]
    priority_score: float
    factors_json:   Optional[str]
    status:         str
    assigned_to:    Optional[str]
    created_at:     datetime

    model_config = {"from_attributes": True}


class AlertUpdateIn(BaseModel):
    status:      Optional[str] = None
    assigned_to: Optional[str] = None


# ── Scenario ──────────────────────────────────────────────────────────────────

class ScenarioParams(BaseModel):
    facility_id:         int
    name:                str = "New Scenario"
    occupancy_pct:       float = 80.0   # % of max capacity
    hvac_setpoint_c:     float = 24.0
    lighting_hours:      float = 12.0
    renewable_pct:       float = 0.0
    water_recycling_pct: float = 0.0
    waste_freq_per_week: float = 3.0
    smart_scheduling:    bool  = False


class ScenarioResult(BaseModel):
    name:                 str
    energy_delta_kwh:     float
    energy_cost_delta_inr:float
    water_delta_litres:   float
    water_cost_delta_inr: float
    co2_delta_kg:         float
    score_delta:          float
    impact_score:         float
    baseline_summary:     dict
    simulated_summary:    dict
