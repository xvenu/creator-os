-- 008_publish_idempotency.sql — deterministic publish intent key + remote receipt.
-- SQLite + Postgres compatible.
ALTER TABLE publish_jobs ADD COLUMN idempotency_key VARCHAR(64) DEFAULT '';
ALTER TABLE publish_jobs ADD COLUMN target_account VARCHAR(128) DEFAULT '';
ALTER TABLE publish_jobs ADD COLUMN content_version VARCHAR(32) DEFAULT 'v1';
ALTER TABLE publish_jobs ADD COLUMN remote_id VARCHAR(256) DEFAULT '';
ALTER TABLE publish_jobs ADD COLUMN remote_status VARCHAR(32) DEFAULT '';
ALTER TABLE publish_jobs ADD COLUMN published_at TIMESTAMP;
CREATE UNIQUE INDEX IF NOT EXISTS ix_publish_jobs_idemkey ON publish_jobs (idempotency_key);
