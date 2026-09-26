# Rollback

Production rollback for Creator-OS. Tested order: stop writers → restore data
(if needed) → roll application back → re-run health + smoke.

## 1. Application rollback

Every service is a container image / checkout at a release tag:

```bash
git fetch --tags
git checkout <previous-release-tag>      # e.g. rollback from v1.1.0 to v1.0.0
docker compose build api worker
docker compose up -d api worker
curl -f http://localhost:8001/health/live     # factory
curl -f http://localhost:8000/api/v1/health/live  # football
curl -f http://localhost:8000/health           # music
```

`release/production-1` branch holds the pinned baseline; release tags
(`v1.x`) are cut only on green CI + smoke.

## 2. Database migration rollback

Migrations are additive SQL with a matching down path:

| Migration | Up | Down |
|---|---|---|
| factory `001_initial` | create tables | `DROP TABLE IF EXISTS production_assets; DROP TABLE IF EXISTS production_requests;` |
| factory `002_universal_factory` | add 8 columns | recreate table without those columns (sqlite: copy-back) or `ALTER TABLE … DROP COLUMN` on Postgres |
| factory `003_asset_requirements` | add 1 column | drop `asset_requirements` |
| music `008_publish_idempotency` | add 6 columns + unique index | `DROP INDEX ix_publish_jobs_idemkey;` + drop columns |
| music `002–007`, football alembic | see files | alembic `downgrade -1` (football); music phases are additive — restore from backup instead of partial down-migration |

Rule: never partially down-migrate a live DB — restore the pre-deploy backup
(`python -m shared.backup restore <dir> --dest ./`) when in doubt.

## 3. Factory version rollback

1. `git checkout <prev-tag> -- zoza-factory` (or full tag checkout).
2. Re-run `CREATE TABLE` guard (`init_db` is additive-only; it never drops).
3. Verify `GET /api/v1/capabilities` contract version still `v2`.
4. Re-run one smoke request per content family before opening traffic.

## 4. Pulse version rollback

Same as §1 per pulse directory. Pulses are independent: rolling back
music-pulse never touches football-pulse or the factory (separate DBs,
separate compose services).

## 5. Failed deployment recovery

1. `docker compose ps` — identify unhealthy service.
2. `docker compose logs --tail=100 <svc>` (no secrets are logged by design).
3. If health fails: roll application back (§1), keep DB as-is (additive).
4. If DB migration failed: restore backup (§2), re-apply up migrations one by one.
5. Re-run smoke: factory capabilities + one `REALITY_FIRST` request + music
   `/ready` + football `/ready`.

## 6. Incompatible contract recovery

Contract V2 is frozen (`CONTRACT_VERSION="v2"`, `test_contract_freeze.py`).
If a v3 is ever introduced: factory keeps accepting v2 via
`normalize_compat` during a deprecation window; pulses pin
`contract_version` in requests; CI fails on duplicate model definitions.
Emergency: check out the last v2-only tag and re-deploy (§1).
