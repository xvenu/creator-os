-- MusicPulse Phase 2 migration (002): normalized market/revenue tables.
-- Applied automatically at startup via Base.metadata.create_all (see app/core/database.py).
-- This file is the auditable SQL equivalent for Postgres production deploys.
CREATE TABLE IF NOT EXISTS country_trends (
  id SERIAL PRIMARY KEY, country VARCHAR(8) NOT NULL, source VARCHAR(32) DEFAULT '',
  title VARCHAR(255) NOT NULL, artist VARCHAR(255) DEFAULT '', rank INTEGER DEFAULT 0,
  score DOUBLE PRECISION DEFAULT 0.0, genre VARCHAR(64) DEFAULT '',
  fetched_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_country_trends_country ON country_trends (country);
CREATE TABLE IF NOT EXISTS genre_analytics (
  id SERIAL PRIMARY KEY, genre VARCHAR(64) NOT NULL, country VARCHAR(8) DEFAULT 'US',
  views INTEGER DEFAULT 0, engagement INTEGER DEFAULT 0, posts INTEGER DEFAULT 0,
  retention DOUBLE PRECISION DEFAULT 0.0, sponsorship_score DOUBLE PRECISION DEFAULT 0.0,
  recorded_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS artist_discovery (
  id SERIAL PRIMARY KEY, artist VARCHAR(255) NOT NULL, genre VARCHAR(64) DEFAULT '',
  country VARCHAR(8) DEFAULT 'US', followers INTEGER DEFAULT 0, streams INTEGER DEFAULT 0,
  velocity DOUBLE PRECISION DEFAULT 0.0, playlist_count INTEGER DEFAULT 0,
  classification VARCHAR(32) DEFAULT 'Emerging', watchlisted BOOLEAN DEFAULT FALSE,
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS sponsors (
  id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL UNIQUE, contact VARCHAR(255) DEFAULT '',
  tier VARCHAR(32) DEFAULT 'standard', active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS campaigns (
  id SERIAL PRIMARY KEY, sponsor_id INTEGER REFERENCES sponsors(id), name VARCHAR(255) NOT NULL,
  package VARCHAR(64) NOT NULL, country VARCHAR(8) DEFAULT 'US', genre VARCHAR(64) DEFAULT '',
  budget DOUBLE PRECISION DEFAULT 0.0, revenue DOUBLE PRECISION DEFAULT 0.0,
  status VARCHAR(32) DEFAULT 'active', starts_at TIMESTAMP DEFAULT NOW(), ends_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS revenue_records (
  id SERIAL PRIMARY KEY, source_type VARCHAR(32) NOT NULL, sponsor_id INTEGER DEFAULT 0,
  campaign_id INTEGER DEFAULT 0, amount DOUBLE PRECISION DEFAULT 0.0,
  country VARCHAR(8) DEFAULT 'US', genre VARCHAR(64) DEFAULT '', platform VARCHAR(32) DEFAULT '',
  recorded_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS competitor_metrics (
  id SERIAL PRIMARY KEY, competitor VARCHAR(128) NOT NULL, platform VARCHAR(32) DEFAULT '',
  post_count INTEGER DEFAULT 0, formats_json TEXT DEFAULT '{}',
  engagement_est INTEGER DEFAULT 0, topics_json TEXT DEFAULT '[]',
  recorded_at TIMESTAMP DEFAULT NOW()
);
