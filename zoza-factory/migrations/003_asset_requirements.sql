-- 003_asset_requirements.sql — pulse-declared acquisition constraints (additive).
ALTER TABLE production_requests ADD COLUMN asset_requirements JSON DEFAULT '{}';
