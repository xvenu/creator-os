# Backups

Tool: `python -m shared.backup` (root). Covers factory DB, music sqlite
fallback, all four shared DBs, plus `.env.example` files and migration SQL
(config metadata). Secret VALUES are never copied.

```bash
python -m shared.backup backup --out ./backups --retention 7
python -m shared.backup verify ./backups/creator-os-<ts>
python -m shared.backup restore ./backups/creator-os-<ts> --dest ./restored
```

- Schedule: daily cron/systemd timer in production (example in deployment runbook).
- Retention: 7 daily backups pruned automatically (`--retention N`).
- Verification: sha256 manifest per file; `verify` fails closed.
- Restore proof: `zoza-factory/tests/test_backup_restore.py` performs
  backup → destroy → restore → ownership/data check in CI.
- Postgres/Redis (production compose): use `pg_dump` + `redis --rdb` in
  addition to this tool; file-level sqlite backup covers dev/test parity.
