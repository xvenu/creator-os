-- 002_universal_factory.sql — content_type + universal pulse fields (additive).
-- SQLite + Postgres compatible. Defaults keep pre-existing rows valid.
ALTER TABLE production_requests ADD COLUMN content_type VARCHAR(16) DEFAULT 'video';
ALTER TABLE production_requests ADD COLUMN format_variant VARCHAR(32) DEFAULT '';
ALTER TABLE production_requests ADD COLUMN aspect_ratio VARCHAR(16) DEFAULT '16:9';
ALTER TABLE production_requests ADD COLUMN resolution VARCHAR(16) DEFAULT '1080p';
ALTER TABLE production_requests ADD COLUMN language VARCHAR(16) DEFAULT 'en';
ALTER TABLE production_requests ADD COLUMN narration TEXT DEFAULT '';
ALTER TABLE production_requests ADD COLUMN brand_context VARCHAR(256) DEFAULT '';
ALTER TABLE production_requests ADD COLUMN call_to_action VARCHAR(256) DEFAULT '';
