"""
backend/db/models.py — SQLAlchemy ORM Models
Mirrors schema.sql exactly (14 tables).
"""

from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum,
    Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.db.database import Base


# ─────────────────────────────────────────────────────
# 1. FacilityType
# ─────────────────────────────────────────────────────
class FacilityType(Base):
    __tablename__ = "facility_types"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(50),  nullable=False, unique=True)
    description = Column(String(255))
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    facilities  = relationship("Facility", back_populates="facility_type")
    thresholds  = relationship("Threshold", back_populates="facility_type")


# ─────────────────────────────────────────────────────
# 2. Facility
# ─────────────────────────────────────────────────────
class Facility(Base):
    __tablename__ = "facilities"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(150), nullable=False)
    city             = Column(String(100), nullable=False)
    state            = Column(String(100), nullable=False)
    facility_type_id = Column(Integer, ForeignKey("facility_types.id"), nullable=False)
    area_sqft        = Column(Float)
    building_count   = Column(Integer, default=1)
    created_at       = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility_type = relationship("FacilityType", back_populates="facilities")
    zones         = relationship("Zone",          back_populates="facility")
    sensors       = relationship("Sensor",        back_populates="facility")


# ─────────────────────────────────────────────────────
# 3. Zone
# ─────────────────────────────────────────────────────
class Zone(Base):
    __tablename__ = "zones"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    facility_id  = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    name         = Column(String(100), nullable=False)
    zone_type    = Column(String(50))
    floor_number = Column(Integer, default=0)
    created_at   = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility = relationship("Facility",      back_populates="zones")
    sensors  = relationship("Sensor",        back_populates="zone")
    readings = relationship("SensorReading", back_populates="zone")
    anomalies= relationship("Anomaly",       back_populates="zone")


# ─────────────────────────────────────────────────────
# 4. Sensor
# ─────────────────────────────────────────────────────
class Sensor(Base):
    __tablename__ = "sensors"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    zone_id     = Column(Integer, ForeignKey("zones.id"))
    metric_type = Column(String(50), nullable=False)
    unit        = Column(String(20), nullable=False)
    description = Column(String(255))
    mac_address = Column(String(20))
    is_active   = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility = relationship("Facility",      back_populates="sensors")
    zone     = relationship("Zone",          back_populates="sensors")
    readings = relationship("SensorReading", back_populates="sensor")
    anomalies= relationship("Anomaly",       back_populates="sensor")


# ─────────────────────────────────────────────────────
# 5. SensorReading
# ─────────────────────────────────────────────────────
class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    sensor_id   = Column(Integer, ForeignKey("sensors.id"),    nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    zone_id     = Column(Integer, ForeignKey("zones.id"))
    metric_type = Column(String(50), nullable=False)
    value       = Column(Float,      nullable=False)
    timestamp   = Column(DateTime,   nullable=False, default=datetime.utcnow)
    source      = Column(Enum("esp32", "synthetic", "manual"), nullable=False, default="synthetic")

    sensor   = relationship("Sensor",   back_populates="readings")
    facility = relationship("Facility")
    zone     = relationship("Zone",     back_populates="readings")

    __table_args__ = (
        Index("idx_readings_main",   "facility_id", "metric_type", "timestamp"),
        Index("idx_readings_sensor", "sensor_id",   "timestamp"),
        Index("idx_readings_ts",     "timestamp"),
    )


# ─────────────────────────────────────────────────────
# 6. Threshold
# ─────────────────────────────────────────────────────
class Threshold(Base):
    __tablename__ = "thresholds"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    facility_type_id = Column(Integer, ForeignKey("facility_types.id"), nullable=False)
    metric_type      = Column(String(50), nullable=False)
    warn_low         = Column(Float)
    warn_high        = Column(Float)
    critical_low     = Column(Float)
    critical_high    = Column(Float)
    unit             = Column(String(20))
    notes            = Column(String(255))

    facility_type = relationship("FacilityType", back_populates="thresholds")

    __table_args__ = (
        UniqueConstraint("facility_type_id", "metric_type", name="uq_type_metric"),
    )


# ─────────────────────────────────────────────────────
# 7. Anomaly
# ─────────────────────────────────────────────────────
class Anomaly(Base):
    __tablename__ = "anomalies"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id        = Column(Integer, ForeignKey("sensors.id"),    nullable=False)
    facility_id      = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    zone_id          = Column(Integer, ForeignKey("zones.id"))
    metric_type      = Column(String(50), nullable=False)
    value            = Column(Float, nullable=False)
    threshold_low    = Column(Float)
    threshold_high   = Column(Float)
    severity         = Column(Enum("low", "medium", "high", "critical"), nullable=False, default="low")
    detected_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at      = Column(DateTime)
    is_resolved      = Column(Boolean, nullable=False, default=False)
    detection_method = Column(Enum("threshold", "z_score", "isolation_forest"), nullable=False, default="threshold")

    sensor   = relationship("Sensor",   back_populates="anomalies")
    facility = relationship("Facility")
    zone     = relationship("Zone",     back_populates="anomalies")
    alert    = relationship("PriorityAlert", back_populates="anomaly", uselist=False)

    __table_args__ = (
        Index("idx_anomaly_facility", "facility_id", "severity",    "detected_at"),
        Index("idx_anomaly_resolved", "facility_id", "is_resolved", "detected_at"),
    )


# ─────────────────────────────────────────────────────
# 8. MLModel
# ─────────────────────────────────────────────────────
class MLModel(Base):
    __tablename__ = "ml_models"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    model_type     = Column(String(50), nullable=False)
    metric_type    = Column(String(50), nullable=False)
    facility_id    = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    model_path     = Column(String(500))
    parameters_json= Column(Text)
    trained_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    accuracy_score = Column(Float)
    is_active      = Column(Boolean, nullable=False, default=True)

    facility  = relationship("Facility")
    forecasts = relationship("Forecast", back_populates="model")

    __table_args__ = (
        Index("idx_model_active", "facility_id", "metric_type", "model_type", "is_active"),
    )


# ─────────────────────────────────────────────────────
# 9. Forecast
# ─────────────────────────────────────────────────────
class Forecast(Base):
    __tablename__ = "forecasts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    facility_id   = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    metric_type   = Column(String(50), nullable=False)
    horizon_hours = Column(Integer, nullable=False, default=24)
    forecast_json = Column(Text,    nullable=False)
    model_used    = Column(String(50), nullable=False, default="prophet")
    generated_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    model_id      = Column(Integer, ForeignKey("ml_models.id"))

    facility = relationship("Facility")
    model    = relationship("MLModel", back_populates="forecasts")

    __table_args__ = (
        Index("idx_forecast_latest", "facility_id", "metric_type", "generated_at"),
    )


# ─────────────────────────────────────────────────────
# 10. Recommendation
# ─────────────────────────────────────────────────────
class Recommendation(Base):
    __tablename__ = "recommendations"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    facility_id       = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    category          = Column(String(50), nullable=False)
    priority_score    = Column(Float, nullable=False, default=50.0)
    title             = Column(String(255), nullable=False)
    description       = Column(Text)
    action_items_json = Column(Text)
    source            = Column(Enum("rule_engine", "llm"), nullable=False, default="rule_engine")
    generated_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_acknowledged   = Column(Boolean, nullable=False, default=False)
    acknowledged_at   = Column(DateTime)

    facility = relationship("Facility")

    __table_args__ = (
        Index("idx_recs_facility", "facility_id", "is_acknowledged", "priority_score"),
    )


# ─────────────────────────────────────────────────────
# 11. PriorityAlert
# ─────────────────────────────────────────────────────
class PriorityAlert(Base):
    __tablename__ = "priority_alerts"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    facility_id    = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    anomaly_id     = Column(Integer, ForeignKey("anomalies.id"))
    title          = Column(String(255), nullable=False)
    description    = Column(Text)
    priority_score = Column(Float, nullable=False, default=0.0)
    factors_json   = Column(Text)
    status         = Column(Enum("open", "in_progress", "resolved"), nullable=False, default="open")
    assigned_to    = Column(String(100))
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at     = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    facility = relationship("Facility")
    anomaly  = relationship("Anomaly",  back_populates="alert")

    __table_args__ = (
        Index("idx_alerts_ranked", "facility_id", "status", "priority_score"),
    )


# ─────────────────────────────────────────────────────
# 12. SimulationRun
# ─────────────────────────────────────────────────────
class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    facility_id     = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    name            = Column(String(100), nullable=False, default="Unnamed Scenario")
    parameters_json = Column(Text, nullable=False)
    results_json    = Column(Text, nullable=False)
    impact_score    = Column(Float)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility = relationship("Facility")

    __table_args__ = (
        Index("idx_sim_facility", "facility_id", "created_at"),
    )


# ─────────────────────────────────────────────────────
# 13. SustainabilityScore
# ─────────────────────────────────────────────────────
class SustainabilityScore(Base):
    __tablename__ = "sustainability_scores"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    facility_id     = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    score_date      = Column(Date,    nullable=False)
    overall_score   = Column(Float,   nullable=False, default=0.0)
    energy_score    = Column(Float,   nullable=False, default=0.0)
    water_score     = Column(Float,   nullable=False, default=0.0)
    waste_score     = Column(Float,   nullable=False, default=0.0)
    air_score       = Column(Float,   nullable=False, default=0.0)
    occupancy_score = Column(Float,   nullable=False, default=0.0)
    details_json    = Column(Text)
    computed_at     = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility = relationship("Facility")

    __table_args__ = (
        UniqueConstraint("facility_id", "score_date", name="uq_score_date"),
        Index("idx_score_history", "facility_id", "score_date"),
    )


# ─────────────────────────────────────────────────────
# 14. ChatHistory
# ─────────────────────────────────────────────────────
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    role        = Column(Enum("user", "assistant"), nullable=False)
    message     = Column(Text, nullable=False)
    source      = Column(Enum("rule_engine", "llm"), nullable=False, default="rule_engine")
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    facility = relationship("Facility")

    __table_args__ = (
        Index("idx_chat_facility", "facility_id", "created_at"),
    )
