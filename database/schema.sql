-- ============================================================
-- SFEID — Sustainable Facility & Estate Intelligence Dashboard
-- MySQL 8.0+ Schema — 14 tables
-- Run this ONCE on a fresh sfeid_db database.
-- ============================================================

CREATE DATABASE IF NOT EXISTS sfeid_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE sfeid_db;

-- ─────────────────────────────────────────────
-- 1. Facility Types
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS facility_types (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- 2. Facilities
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS facilities (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    city             VARCHAR(100) NOT NULL,
    state            VARCHAR(100) NOT NULL,
    facility_type_id INT          NOT NULL,
    area_sqft        FLOAT,
    building_count   INT          DEFAULT 1,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_type_id) REFERENCES facility_types(id)
);

-- ─────────────────────────────────────────────
-- 3. Zones
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zones (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    facility_id  INT          NOT NULL,
    name         VARCHAR(100) NOT NULL,
    zone_type    VARCHAR(50),   -- classroom, lab, canteen, parking, hostel, admin_block, etc.
    floor_number INT          DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id)
);

-- ─────────────────────────────────────────────
-- 4. Sensors
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sensors (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    facility_id  INT          NOT NULL,
    zone_id      INT,
    metric_type  VARCHAR(50)  NOT NULL,
    unit         VARCHAR(20)  NOT NULL,
    description  VARCHAR(255),
    mac_address  VARCHAR(20),
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    FOREIGN KEY (zone_id)     REFERENCES zones(id)
);

-- ─────────────────────────────────────────────
-- 5. Sensor Readings  (primary time-series table)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sensor_readings (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id   INT        NOT NULL,
    facility_id INT        NOT NULL,
    zone_id     INT,
    metric_type VARCHAR(50) NOT NULL,
    value       FLOAT      NOT NULL,
    timestamp   DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source      ENUM('esp32','synthetic','manual') NOT NULL DEFAULT 'synthetic',
    FOREIGN KEY (sensor_id)   REFERENCES sensors(id),
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_readings_main  (facility_id, metric_type, timestamp DESC),
    INDEX idx_readings_sensor (sensor_id, timestamp DESC),
    INDEX idx_readings_ts     (timestamp DESC)
);

-- ─────────────────────────────────────────────
-- 6. Configurable Thresholds
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS thresholds (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    facility_type_id INT          NOT NULL,
    metric_type      VARCHAR(50)  NOT NULL,
    warn_low         FLOAT,
    warn_high        FLOAT,
    critical_low     FLOAT,
    critical_high    FLOAT,
    unit             VARCHAR(20),
    notes            VARCHAR(255),
    FOREIGN KEY (facility_type_id) REFERENCES facility_types(id),
    UNIQUE KEY uq_type_metric (facility_type_id, metric_type)
);

-- ─────────────────────────────────────────────
-- 7. Anomalies
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anomalies (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    sensor_id        INT        NOT NULL,
    facility_id      INT        NOT NULL,
    zone_id          INT,
    metric_type      VARCHAR(50) NOT NULL,
    value            FLOAT      NOT NULL,
    threshold_low    FLOAT,
    threshold_high   FLOAT,
    severity         ENUM('low','medium','high','critical') NOT NULL DEFAULT 'low',
    detected_at      DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at      DATETIME,
    is_resolved      BOOLEAN    NOT NULL DEFAULT FALSE,
    detection_method ENUM('threshold','z_score','isolation_forest') NOT NULL DEFAULT 'threshold',
    FOREIGN KEY (sensor_id)   REFERENCES sensors(id),
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_anomaly_facility (facility_id, severity, detected_at DESC),
    INDEX idx_anomaly_resolved (facility_id, is_resolved, detected_at DESC)
);

-- ─────────────────────────────────────────────
-- 8. ML Model Registry
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_models (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    model_type     VARCHAR(50)  NOT NULL,  -- isolation_forest, prophet, linear_regression
    metric_type    VARCHAR(50)  NOT NULL,
    facility_id    INT          NOT NULL,
    model_path     VARCHAR(500),
    parameters_json TEXT,
    trained_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accuracy_score FLOAT,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_model_active (facility_id, metric_type, model_type, is_active)
);

-- ─────────────────────────────────────────────
-- 9. Forecasts
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS forecasts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    facility_id     INT         NOT NULL,
    metric_type     VARCHAR(50) NOT NULL,
    horizon_hours   INT         NOT NULL DEFAULT 24,
    forecast_json   LONGTEXT    NOT NULL,
    model_used      VARCHAR(50) NOT NULL DEFAULT 'prophet',
    generated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_id        INT,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    FOREIGN KEY (model_id)    REFERENCES ml_models(id),
    INDEX idx_forecast_latest (facility_id, metric_type, generated_at DESC)
);

-- ─────────────────────────────────────────────
-- 10. Recommendations
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendations (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    facility_id      INT          NOT NULL,
    category         VARCHAR(50)  NOT NULL,  -- energy, water, air, waste, occupancy
    priority_score   FLOAT        NOT NULL DEFAULT 50.0,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    action_items_json TEXT,
    source           ENUM('rule_engine','llm') NOT NULL DEFAULT 'rule_engine',
    generated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_acknowledged  BOOLEAN      NOT NULL DEFAULT FALSE,
    acknowledged_at  DATETIME,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_recs_facility (facility_id, is_acknowledged, priority_score DESC)
);

-- ─────────────────────────────────────────────
-- 11. Priority Alerts
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS priority_alerts (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    facility_id    INT          NOT NULL,
    anomaly_id     INT,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    priority_score FLOAT        NOT NULL DEFAULT 0.0,
    factors_json   TEXT,
    status         ENUM('open','in_progress','resolved') NOT NULL DEFAULT 'open',
    assigned_to    VARCHAR(100),
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    FOREIGN KEY (anomaly_id)  REFERENCES anomalies(id),
    INDEX idx_alerts_ranked (facility_id, status, priority_score DESC)
);

-- ─────────────────────────────────────────────
-- 12. Simulation Runs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS simulation_runs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    facility_id     INT          NOT NULL,
    name            VARCHAR(100) NOT NULL DEFAULT 'Unnamed Scenario',
    parameters_json TEXT         NOT NULL,
    results_json    LONGTEXT     NOT NULL,
    impact_score    FLOAT,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_sim_facility (facility_id, created_at DESC)
);

-- ─────────────────────────────────────────────
-- 13. Sustainability Scores  (daily snapshot)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sustainability_scores (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    facility_id     INT      NOT NULL,
    score_date      DATE     NOT NULL,
    overall_score   FLOAT    NOT NULL DEFAULT 0.0,
    energy_score    FLOAT    NOT NULL DEFAULT 0.0,
    water_score     FLOAT    NOT NULL DEFAULT 0.0,
    waste_score     FLOAT    NOT NULL DEFAULT 0.0,
    air_score       FLOAT    NOT NULL DEFAULT 0.0,
    occupancy_score FLOAT    NOT NULL DEFAULT 0.0,
    details_json    TEXT,
    computed_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    UNIQUE KEY uq_score_date (facility_id, score_date),
    INDEX idx_score_history (facility_id, score_date DESC)
);

-- ─────────────────────────────────────────────
-- 14. Chat History
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    facility_id INT         NOT NULL,
    role        ENUM('user','assistant') NOT NULL,
    message     TEXT        NOT NULL,
    source      ENUM('rule_engine','llm') NOT NULL DEFAULT 'rule_engine',
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities(id),
    INDEX idx_chat_facility (facility_id, created_at ASC)
);

-- ============================================================
-- SEED: Facility Types
-- ============================================================
INSERT IGNORE INTO facility_types (name, description) VALUES
  ('engineering_college', 'Engineering and technical educational institutions'),
  ('hospital',            'Healthcare and medical facilities'),
  ('corporate_campus',    'Corporate offices and business parks'),
  ('industrial',          'Manufacturing and industrial estates'),
  ('municipal',           'Government and municipal buildings');

-- ============================================================
-- SEED: Demo Facility — SFEID College of Engineering
-- ============================================================
INSERT IGNORE INTO facilities (id, name, city, state, facility_type_id, area_sqft, building_count) VALUES
  (1, 'SFEID College of Engineering', 'Pune', 'Maharashtra', 1, 850000, 8);

-- ============================================================
-- SEED: Zones
-- ============================================================
INSERT IGNORE INTO zones (id, facility_id, name, zone_type, floor_number) VALUES
  (1, 1, 'Main Academic Building', 'classroom',   1),
  (2, 1, 'Computer & Electronics Lab', 'lab',     1),
  (3, 1, 'Central Canteen',        'canteen',     0),
  (4, 1, 'Main Parking Lot',       'parking',     0),
  (5, 1, 'Hostel Block A',         'hostel',      1),
  (6, 1, 'Administrative Block',   'admin_block', 1);

-- ============================================================
-- SEED: Sensors  (one representative sensor per metric)
-- ============================================================
INSERT IGNORE INTO sensors (id, facility_id, zone_id, metric_type, unit, description, mac_address) VALUES
  (1,  1, 1, 'energy_kwh',       'kWh',      'Main building smart energy meter',   'AA:BB:CC:DD:EE:01'),
  (2,  1, 2, 'pm25',             'µg/m³',    'Lab air quality — PM2.5',            'AA:BB:CC:DD:EE:02'),
  (3,  1, 2, 'pm10',             'µg/m³',    'Lab air quality — PM10',             'AA:BB:CC:DD:EE:03'),
  (4,  1, 3, 'water_litres',     'L',        'Canteen water flow meter',           'AA:BB:CC:DD:EE:04'),
  (5,  1, 3, 'bin_fill_pct',     '%',        'Canteen waste bin ultrasonic sensor','AA:BB:CC:DD:EE:05'),
  (6,  1, 1, 'temperature_c',    '°C',       'Main building HVAC temperature',     'AA:BB:CC:DD:EE:06'),
  (7,  1, 1, 'humidity_pct',     '%',        'Main building humidity sensor',      'AA:BB:CC:DD:EE:07'),
  (8,  1, 1, 'occupancy_count',  'count',    'Main entrance occupancy counter',    'AA:BB:CC:DD:EE:08'),
  (9,  1, 4, 'parking_count',    'count',    'Parking lot vehicle counter',        'AA:BB:CC:DD:EE:09'),
  (10, 1, 2, 'equipment_util_pct','%',       'Lab equipment utilisation tracker',  'AA:BB:CC:DD:EE:10');

-- ============================================================
-- SEED: Thresholds for engineering_college (facility_type_id=1)
-- ============================================================
INSERT IGNORE INTO thresholds
  (facility_type_id, metric_type,    warn_low, warn_high, critical_low, critical_high, unit,    notes) VALUES
  (1, 'energy_kwh',       NULL,  70.0,  NULL,  90.0,  'kWh',   'Per hour — based on campus load profile'),
  (1, 'pm25',             NULL,  35.0,  NULL,  60.0,  'µg/m³', 'WHO 24h guideline: 15; CPCB 24h: 60'),
  (1, 'pm10',             NULL,  60.0,  NULL, 100.0,  'µg/m³', 'CPCB 24h standard: 100'),
  (1, 'water_litres',     NULL, 800.0,  NULL,1200.0,  'L',     'Per hour — campus consumption model'),
  (1, 'bin_fill_pct',     NULL,  75.0,  NULL,  90.0,  '%',     'Alert for collection at 75%, critical at 90%'),
  (1, 'temperature_c',   16.0,  32.0,  10.0,  38.0,  '°C',    'Comfort range 18–28°C'),
  (1, 'humidity_pct',    25.0,  75.0,  15.0,  85.0,  '%',     'Comfort range 30–70%'),
  (1, 'occupancy_count',  NULL,4500.0,  NULL,5000.0,  'count', 'Campus capacity ~5000'),
  (1, 'parking_count',    NULL, 400.0,  NULL, 500.0,  'count', 'Parking capacity ~500 vehicles'),
  (1, 'equipment_util_pct',NULL, 85.0,  NULL,  95.0,  '%',     'High utilisation may indicate scheduling issues');
