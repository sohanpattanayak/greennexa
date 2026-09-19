# SFEID — Sustainable Facility & Estate Intelligence Dashboard

> A full-stack IoT-enabled facility management system for Indian institutional campuses,
> built as a hackathon prototype using Streamlit, FastAPI, MySQL, scikit-learn, and Prophet.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit 1.37 |
| Backend | FastAPI 0.115 |
| Database | MySQL 8.0 (local, via MySQL Workbench) |
| Charts | Plotly 5.22 |
| ML — Anomaly | scikit-learn (Isolation Forest) |
| ML — Forecast | Prophet 1.1 (primary) |
| AI/LLM | Gemini (optional, rule-based fallback) |

---

## Quick Start

### 1. Set up MySQL

1. Open MySQL Workbench and connect to your local MySQL instance.
2. Run the schema script:
   ```sql
   SOURCE C:/path/to/sfeid/database/schema.sql;
   ```

### 2. Configure environment

```bash
copy .env.example .env
# Edit .env with your MySQL password and any other settings
```

### 3. Install backend dependencies

> **Windows — Prophet installation (choose one):**
> ```bash
> # Option A (recommended — no C++ compiler needed):
> conda install -c conda-forge prophet
>
> # Option B (requires Microsoft C++ Build Tools):
> pip install prophet
> ```

```bash
cd backend
pip install -r requirements.txt
```

### 4. Generate seed data (7-day history)

```bash
# From the project root (sfeid/)
python database/generate_seed.py
```

### 5. Start the backend

```bash
# From the project root (sfeid/)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Verify at: http://localhost:8000/docs

### 6. Install frontend dependencies

```bash
cd frontend
pip install -r requirements.txt
```

### 7. Start the Streamlit frontend

```bash
# From the frontend/ directory
streamlit run app.py --server.port 8501
```

Open: http://localhost:8501
Default password: `sfeid2026`

---

## Project Structure

```
sfeid/
├── backend/          FastAPI app (routers, services, ML, DB)
├── frontend/         Streamlit app (10 pages, utils)
├── database/         schema.sql + seed data generator
├── data_simulator/   ESP32 mock script
├── docs/             Setup guide, API reference
├── .env.example      Environment template
└── README.md
```

---

## Demo Facility

The seed data creates **SFEID College of Engineering** (Pune, Maharashtra) with:
- 6 zones (classroom, lab, canteen, parking, hostel, admin)
- 10 sensors (one per metric)
- 7 days of realistic historical data
- Synthetic generator adds a new reading every 60 seconds

All synthetic rows are labelled **🔵 DEMO** in the UI.

---

## Metrics Tracked

| Metric | Unit | Zone |
|---|---|---|
| Energy consumption | kWh | Main building |
| PM2.5 air quality | µg/m³ | Lab |
| PM10 air quality | µg/m³ | Lab |
| Water usage | L | Canteen |
| Waste bin fill | % | Canteen |
| Temperature | °C | Main building |
| Humidity | % | Main building |
| Occupancy | count | Main entrance |
| Parking | vehicles | Parking lot |
| Equipment utilisation | % | Lab |

---

## AI Features (No API Key Required)

- **Anomaly Detection** — Isolation Forest + Z-score (scikit-learn)
- **Forecasting** — Prophet 24-hour forecast with confidence intervals
- **Recommendations** — Rule-based engine (10+ templates per metric)
- **Priority Engine** — Weighted deterministic scoring
- **Scenario Simulation** — Formula-based what-if analysis
- **Admin Chat** — Keyword intent matching + template responses

**Optional Gemini LLM Enhancement**: Set `GEMINI_API_KEY` in `.env` to enable
AI-enhanced recommendations and natural-language chat.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PASSWORD` | — | MySQL password (**required**) |
| `DB_NAME` | `sfeid_db` | Database name |
| `ADMIN_PASSWORD` | `sfeid2026` | Streamlit login password |
| `SYNTHETIC_ENABLED` | `true` | Auto-generate demo data |
| `SYNTHETIC_INTERVAL_SECONDS` | `60` | Feed interval |
| `GEMINI_API_KEY` | *(empty)* | Optional — activates LLM mode |
| `ELECTRICITY_TARIFF_INR_PER_KWH` | `8.0` | For scenario cost estimates |
| `WATER_TARIFF_INR_PER_KL` | `15.0` | For scenario cost estimates |
