# 🛠️ SFEID Setup & Administration Guide

## System Requirements

- **Operating System**: Windows 10/11 (or Linux/macOS)
- **Python**: 3.10+
- **MySQL Server**: 8.0+ (with MySQL Workbench)
- **C++ Build Tools** (Optional for Windows pip Prophet install; conda recommended)

---

## 1. Database Setup

1. Open **MySQL Workbench**.
2. Connect to your local MySQL instance.
3. Open `database/schema.sql` and execute the entire script to create the `sfeid_db` schema, 14 tables, indexes, and baseline seed data.

---

## 2. Environment Configuration

1. Copy `.env.example` to `.env` in the project root.
2. Configure your local MySQL password and settings:
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_actual_mysql_password
   DB_NAME=sfeid_db

   ADMIN_PASSWORD=sfeid2026
   SYNTHETIC_ENABLED=true
   SYNTHETIC_INTERVAL_SECONDS=60
   GEMINI_API_KEY=
   ```

---

## 3. Python Environment & Dependencies

### Prophet Installation on Windows

```bash
# Recommended approach using conda:
conda install -c conda-forge prophet

# Alternative using pip (requires Microsoft C++ Build Tools):
pip install prophet
```

### Install Project Requirements

```bash
cd backend
pip install -r requirements.txt

cd ../frontend
pip install -r requirements.txt
```

---

## 4. Historical Seed Data Generation

Populate 7 days of realistic 5-minute interval historical readings (~200,000 database rows):

```bash
# Run from project root directory
python database/generate_seed.py
```

---

## 5. Running the Application

### Start FastAPI Backend

```bash
# From project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive API documentation: `http://localhost:8000/docs`

### Start Streamlit Frontend

```bash
# From frontend/ directory
cd frontend
streamlit run app.py --server.port 8501
```
Dashboard URL: `http://localhost:8501`
Default Login Password: `sfeid2026`

---

## 6. (Optional) Run ESP32 Mock Hardware Simulator

To simulate live physical ESP32 sensors sending telemetry via HTTP POST:

```bash
python data_simulator/mock_esp32.py
```
