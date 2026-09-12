-- 001_initial.sql — zoza-factory foundation (mirrors app/models/production.py).
-- SQLite + Postgres compatible.
CREATE TABLE IF NOT EXISTS production_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id VARCHAR(128) UNIQUE NOT NULL,
    pulse VARCHAR(64) DEFAULT '',
    goal TEXT DEFAULT '',
    style VARCHAR(64) DEFAULT '',
    length_seconds INTEGER DEFAULT 0,
    urgency VARCHAR(16) DEFAULT 'normal',
    production_mode VARCHAR(16) DEFAULT 'REALITY_FIRST',
    ai_generation_allowed BOOLEAN DEFAULT FALSE,
    sources JSON DEFAULT '[]',
    evidence JSON DEFAULT '[]',
    voice_profile VARCHAR(64) DEFAULT '',
    target_audience VARCHAR(128) DEFAULT '',
    priority INTEGER DEFAULT 0,
    state VARCHAR(16) DEFAULT 'created',
    strategy_json JSON DEFAULT '{}',
    timeline_json JSON DEFAULT '{}',
    export_json JSON DEFAULT '{}',
    error TEXT DEFAULT '',
    render_seconds FLOAT DEFAULT 0.0,
    export_seconds FLOAT DEFAULT 0.0,
    created_at FLOAT DEFAULT 0,
    updated_at FLOAT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_production_requests_state ON production_requests (state);

CREATE TABLE IF NOT EXISTS production_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id VARCHAR(128) UNIQUE NOT NULL,
    kind VARCHAR(32) DEFAULT 'real_photo',
    category VARCHAR(64) DEFAULT '',
    source VARCHAR(256) DEFAULT '',
    license VARCHAR(128) DEFAULT '',
    trust_score FLOAT DEFAULT 0.0,
    rights_status VARCHAR(16) DEFAULT 'UNKNOWN',
    duration_seconds FLOAT DEFAULT 0.0,
    meta_json JSON DEFAULT '{}',
    acquired_at FLOAT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_production_assets_kind ON production_assets (kind);
