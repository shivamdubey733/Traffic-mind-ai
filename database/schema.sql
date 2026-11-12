-- TrafficMind AI Database Schema (SQLite)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT DEFAULT 'traffic_operator',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS traffic_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL, -- NORTH, EAST, SOUTH, WEST
    vehicle_count INTEGER NOT NULL,
    queue_length INTEGER NOT NULL,
    density_pct REAL NOT NULL,
    cars INTEGER DEFAULT 0,
    motorcycles INTEGER DEFAULT 0,
    buses INTEGER DEFAULT 0,
    trucks INTEGER DEFAULT 0,
    bicycles INTEGER DEFAULT 0,
    is_peak INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vehicle_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    track_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL,
    queue_length INTEGER NOT NULL,
    waiting_time_sec REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL,
    state TEXT NOT NULL, -- RED, YELLOW, GREEN, ALL_RED
    duration_sec INTEGER NOT NULL,
    reason TEXT DEFAULT 'adaptive_cycle', -- adaptive_cycle, emergency_override, min_green_clearance
    is_emergency INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ambulance_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL,
    status TEXT NOT NULL, -- DETECTED, PRIORITY_ACTIVE, CLEARED
    priority_granted_at TIMESTAMP,
    cleared_at TIMESTAMP,
    detection_mode TEXT DEFAULT 'manual_simulation' -- yolo_vision, manual_simulation
);

CREATE TABLE IF NOT EXISTS prediction_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lane TEXT NOT NULL,
    horizon_minutes INTEGER NOT NULL, -- 5, 10, 15
    predicted_demand INTEGER NOT NULL,
    predicted_queue INTEGER NOT NULL,
    actual_demand INTEGER,
    model_version TEXT DEFAULT 'v1.0-rf'
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for lightning fast queries and analytics
CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON traffic_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_traffic_lane ON traffic_records(lane);
CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON signal_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_prediction_timestamp ON prediction_records(timestamp);
