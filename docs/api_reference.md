# 📡 SFEID API Reference Summary

The SFEID FastAPI backend exposes **39 RESTful endpoints** categorized across 8 routers.

---

## 1. Ingestion Router (`/ingest`)

- `POST /ingest/sensor` — Ingest batch sensor telemetry (ESP32 / hardware payload).
- `POST /ingest/sensor/single` — Ingest single sensor reading.
- `POST /ingest/manual` — Record admin manual meter entry (`source='manual'`).
- `POST /ingest/synthetic/toggle` — Start or stop background synthetic data generator.
- `GET /ingest/synthetic/status` — Get synthetic generator running status.

---

## 2. Sensors & Readings Routers (`/sensors`, `/readings`)

- `GET /sensors/` — List active sensors for a facility.
- `GET /sensors/{id}/latest` — Get latest single reading for a sensor.
- `GET /readings/live` — Get latest reading for every metric (KPI tile feed).
- `GET /readings/` — Historical time-range query with filtering and limits.

---

## 3. Analytics Router (`/analytics`)

- `GET /analytics/trends` — Aggregated hourly/daily time-series metrics.
- `GET /analytics/anomalies` — List detected anomaly events (filtered by status/severity).
- `POST /analytics/anomalies/detect` — Trigger 3-tier anomaly detection pipeline manually.
- `GET /analytics/forecast` — Retrieve 24-hour Prophet forecast with confidence bounds.
- `POST /analytics/forecast/generate` — Force re-train Prophet/Linear Regression models.
- `GET /analytics/summary` — 24-hour min/max/avg/latest summary statistics per metric.

---

## 4. Priority Engine Router (`/priority`)

- `GET /priority/alerts` — List ranked incident alerts.
- `POST /priority/run` — Trigger multi-factor MinMaxScaler re-scoring.
- `PATCH /priority/alerts/{id}` — Update alert status (`open`, `in_progress`, `resolved`) or assignment.

---

## 5. Scores Router (`/scores`)

- `GET /scores/sustainability` — Get today's sustainability score (0–100) and grade.
- `GET /scores/history` — 30-day historical sustainability score log.
- `POST /scores/compute` — Force re-compute today's score.

---

## 6. AI & Voice Router (`/ai`)

- `GET /ai/status` — Check AI mode (`Rule-based` vs `LLM-enhanced`).
- `POST /ai/recommendations/generate` — Trigger rule-based (+ optional Gemini) recommendation engine.
- `GET /ai/recommendations/` — List operational recommendations.
- `PATCH /ai/recommendations/{id}/acknowledge` — Mark recommendation as acknowledged.
- `POST /ai/chat` — Send text message to AI Admin Assistant.
- `POST /ai/voice` — Upload audio file for SpeechRecognition transcription + chat response.
- `GET /ai/chat/history` — Retrieve chat message log.

---

## 7. Scenario Simulation Router (`/scenario`)

- `POST /scenario/simulate` — Run what-if policy simulation delta calculations.
- `POST /scenario/simulate/save` — Run and persist simulation run to database.
- `GET /scenario/runs` — List saved simulation runs.
- `DELETE /scenario/runs/{id}` — Delete a saved run.

---

## 8. Admin Router (`/admin`)

- `POST /admin/auth/verify` — Verify password for Streamlit login gate.
- `GET /admin/facilities` — List all facilities.
- `POST /admin/facilities` — Create a new facility.
- `DELETE /admin/facilities/{id}` — Delete a facility.
- `GET /admin/zones` — List zones for a facility.
- `POST /admin/zones` — Create a zone.
- `GET /admin/thresholds` — Get metric warning/critical thresholds.
- `PUT /admin/thresholds/{id}` — Update metric threshold values.
