-- MusicPulse Phase 6 migration (005): Creator-OS video pipeline tables.
-- Auto-applied at startup via Base.metadata.create_all; SQL for Postgres deploys.
CREATE TABLE IF NOT EXISTS content_packages (
  id VARCHAR(64) PRIMARY KEY, type VARCHAR(32) NOT NULL, title VARCHAR(255) NOT NULL,
  summary TEXT DEFAULT '', script TEXT DEFAULT '', hashtags_json TEXT DEFAULT '[]',
  keywords_json TEXT DEFAULT '[]', thumbnail_brief TEXT DEFAULT '', video_brief TEXT DEFAULT '',
  target_market VARCHAR(8) DEFAULT 'US', target_platform VARCHAR(32) DEFAULT 'youtube',
  priority_score DOUBLE PRECISION DEFAULT 0.0, predicted_views DOUBLE PRECISION DEFAULT 0.0,
  predicted_revenue DOUBLE PRECISION DEFAULT 0.0, generated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS package_exports (
  id SERIAL PRIMARY KEY, package_id VARCHAR(64) NOT NULL, channel VARCHAR(16) NOT NULL,
  status VARCHAR(16) DEFAULT 'sent', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS zoza_jobs (
  id SERIAL PRIMARY KEY, package_id VARCHAR(64) NOT NULL, state VARCHAR(16) DEFAULT 'created',
  attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS render_results (
  id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL, video_url VARCHAR(512) DEFAULT '',
  duration_sec INTEGER DEFAULT 0, success BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS publish_results (
  id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL, platform VARCHAR(32) DEFAULT '',
  external_id VARCHAR(128) DEFAULT '', success BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS video_metrics (
  id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL, views INTEGER DEFAULT 0,
  watch_time_sec INTEGER DEFAULT 0, revenue DOUBLE PRECISION DEFAULT 0.0,
  ctr DOUBLE PRECISION DEFAULT 0.0, retention DOUBLE PRECISION DEFAULT 0.0,
  audience_growth INTEGER DEFAULT 0, engagement INTEGER DEFAULT 0,
  recorded_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS event_bus_events (
  id SERIAL PRIMARY KEY, event_type VARCHAR(32) NOT NULL,
  source_pulse VARCHAR(64) DEFAULT 'music-pulse', payload_json TEXT DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS shared_knowledge (
  id SERIAL PRIMARY KEY, domain VARCHAR(32) NOT NULL, key VARCHAR(255) NOT NULL,
  value_json TEXT DEFAULT '{}', source_pulse VARCHAR(64) DEFAULT 'music-pulse',
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS feedback_events (
  id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL, kind VARCHAR(32) NOT NULL,
  value DOUBLE PRECISION DEFAULT 0.0, created_at TIMESTAMP DEFAULT NOW()
);
