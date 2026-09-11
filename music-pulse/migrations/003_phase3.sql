-- MusicPulse Phase 3 migration (003): autonomous company tables.
-- Auto-applied at startup via Base.metadata.create_all; SQL for Postgres deploys.
CREATE TABLE IF NOT EXISTS executive_goals (
  id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, category VARCHAR(32) DEFAULT 'growth',
  target DOUBLE PRECISION DEFAULT 0.0, current DOUBLE PRECISION DEFAULT 0.0,
  status VARCHAR(32) DEFAULT 'active', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS strategic_plans (
  id SERIAL PRIMARY KEY, horizon VARCHAR(16) NOT NULL, markets_json TEXT DEFAULT '[]',
  genres_json TEXT DEFAULT '[]', artists_json TEXT DEFAULT '[]', posting_volume INTEGER DEFAULT 0,
  revenue_target DOUBLE PRECISION DEFAULT 0.0, growth_target DOUBLE PRECISION DEFAULT 0.0,
  rationale TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS business_memory (
  id SERIAL PRIMARY KEY, kind VARCHAR(32) NOT NULL, title VARCHAR(255) NOT NULL,
  body TEXT DEFAULT '', score DOUBLE PRECISION DEFAULT 0.0,
  ref_type VARCHAR(64) DEFAULT '', ref_id VARCHAR(64) DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS opportunity_scores (
  id SERIAL PRIMARY KEY, key VARCHAR(255) NOT NULL, category VARCHAR(32) NOT NULL,
  impact DOUBLE PRECISION DEFAULT 0.0, rationale TEXT DEFAULT '',
  allocated BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS executive_decisions (
  id SERIAL PRIMARY KEY, question VARCHAR(512) NOT NULL, options_json TEXT DEFAULT '[]',
  chosen VARCHAR(255) DEFAULT '', rationale TEXT DEFAULT '',
  memory_refs_json TEXT DEFAULT '[]', outcome VARCHAR(32) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS policy_events (
  id SERIAL PRIMARY KEY, rule VARCHAR(64) NOT NULL, verdict VARCHAR(16) NOT NULL,
  content_ref VARCHAR(128) DEFAULT '', detail TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS autonomy_cycles (
  id SERIAL PRIMARY KEY, status VARCHAR(32) DEFAULT 'completed', stages_json TEXT DEFAULT '{}',
  error TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS optimization_results (
  id SERIAL PRIMARY KEY, scope VARCHAR(32) NOT NULL, recommendation TEXT DEFAULT '',
  expected_uplift DOUBLE PRECISION DEFAULT 0.0, created_at TIMESTAMP DEFAULT NOW()
);
