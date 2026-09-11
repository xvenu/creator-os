-- MusicPulse Phase 8 migration (007): refactor mirrors.
-- Runtime cross-pulse state lives in shared/*.db; these mirror audit/API needs.
CREATE TABLE IF NOT EXISTS exported_assets (
  asset_id VARCHAR(64) PRIMARY KEY, video VARCHAR(512) DEFAULT '',
  thumbnail VARCHAR(512) DEFAULT '', title VARCHAR(255) DEFAULT '',
  description TEXT DEFAULT '', hashtags_json TEXT DEFAULT '[]',
  metadata_json TEXT DEFAULT '{}', published BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS notification_events (
  id SERIAL PRIMARY KEY, event VARCHAR(32) NOT NULL,
  source_pulse VARCHAR(64) DEFAULT 'music-pulse', message TEXT DEFAULT '',
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS pulse_registrations (
  id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL, role VARCHAR(16) DEFAULT 'pulse',
  status VARCHAR(16) DEFAULT 'active', created_at TIMESTAMP DEFAULT NOW()
);
-- factory_jobs: Zoza-owned runtime state, observed via jobs/*.json polling.
-- No table created here by design; zoza_jobs (Phase 6) remains the Pulse-side record.
