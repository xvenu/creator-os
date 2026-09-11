-- MusicPulse Phase 7 migration (006): reality-first intelligence tables.
-- Auto-applied at startup via Base.metadata.create_all; SQL for Postgres deploys.
-- ContentPackage evidence extension is additive ALTERs (safe on existing rows).
CREATE TABLE IF NOT EXISTS sources (
  id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, url VARCHAR(512) DEFAULT '',
  kind VARCHAR(32) NOT NULL, official BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS source_scores (
  id SERIAL PRIMARY KEY, source_id INTEGER NOT NULL, trust DOUBLE PRECISION DEFAULT 0.0,
  freshness DOUBLE PRECISION DEFAULT 0.0, authority DOUBLE PRECISION DEFAULT 0.0,
  reliability DOUBLE PRECISION DEFAULT 0.0, recorded_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS evidence_records (
  id SERIAL PRIMARY KEY, claim VARCHAR(512) NOT NULL, source_id INTEGER DEFAULT 0,
  url VARCHAR(512) DEFAULT '', snippet TEXT DEFAULT '', recorded_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS media_assets (
  id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, kind VARCHAR(32) NOT NULL,
  ref_url VARCHAR(512) DEFAULT '', rights_status VARCHAR(32) DEFAULT 'unknown',
  attribution VARCHAR(255) DEFAULT '', source_id INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS verification_events (
  id SERIAL PRIMARY KEY, subject VARCHAR(512) NOT NULL, category VARCHAR(32) NOT NULL,
  verdict VARCHAR(32) NOT NULL, rationale TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS artist_profiles (
  id SERIAL PRIMARY KEY, artist VARCHAR(255) NOT NULL UNIQUE, label VARCHAR(255) DEFAULT '',
  genre VARCHAR(64) DEFAULT '', bio_ref VARCHAR(512) DEFAULT '',
  momentum DOUBLE PRECISION DEFAULT 0.0, coverage INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS label_profiles (
  id SERIAL PRIMARY KEY, label VARCHAR(255) NOT NULL UNIQUE, kind VARCHAR(32) DEFAULT 'independent',
  signings INTEGER DEFAULT 0, releases INTEGER DEFAULT 0,
  activity DOUBLE PRECISION DEFAULT 0.0, updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS newsroom_reports (
  id SERIAL PRIMARY KEY, kind VARCHAR(32) NOT NULL, title VARCHAR(255) NOT NULL,
  body TEXT DEFAULT '', sources_json TEXT DEFAULT '[]',
  verification VARCHAR(32) DEFAULT 'unverified', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS documentary_projects (
  id SERIAL PRIMARY KEY, subject VARCHAR(255) NOT NULL, brief TEXT DEFAULT '',
  script TEXT DEFAULT '', research_json TEXT DEFAULT '{}',
  package_id VARCHAR(64) DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rights_records (
  id SERIAL PRIMARY KEY, asset_id INTEGER NOT NULL, restriction VARCHAR(255) DEFAULT '',
  license VARCHAR(128) DEFAULT 'unknown', owner VARCHAR(255) DEFAULT '',
  attribution_required BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS evidence_json TEXT DEFAULT '[]';
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS sources_json TEXT DEFAULT '[]';
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS verification_status VARCHAR(32) DEFAULT 'unverified';
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION DEFAULT 0.0;
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS rights_status VARCHAR(32) DEFAULT 'unknown';
ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS attribution_json TEXT DEFAULT '[]';
