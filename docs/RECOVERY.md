# Recovery / restart-resume state machines

## Zoza Factory request lifecycle (persisted, resumable)

```
created → planned → acquiring → assembling → rendering → exported
   │         │           │            │             │            │
   └─────────┴───────────┴────────────┴─────────────┴──▶ failed (error capped, notified)
```

- Every transition commits the row (`state`, `updated_at`) before doing work.
- Crash between plan and execute → row stays `planned` (observable via
  `GET /requests/{id}`); re-`POST …/execute` resumes deterministically to the
  same artifact paths (proven in `test_recovery.py`).
- Crash during render → row stays `rendering`; re-execute re-renders (same
  outputs, no forked jobs — one row per `request_id`, 409 on duplicates).
- Failure → `failed` + `error` + `notify_failure` (fail-open); never silent.
- Factory unreachable (pulse side) → pulse row stays `queued` with
  `factory-unreachable, retryable=True`; autonomy loops continue.

## MusicPulse publishing (persisted, idempotent)

`queued → sending → sent | failed → (backoff) → sending …`
Same `idempotency_key` never double-sends: sent rows are skipped on resume
(`test_publish_idempotency.py`). 429s get extended (≥15 min) backoff.

## FootballPulse deliveries (persisted, idempotent)

`queued → sending → sent | failed → (backoff) → …`, same guarantees
(`test_publication_idempotency.py`).

## Queue / network / DB interruptions

- Redis/RQ outage: jobs remain in DB (`queued`/`failed`); workers pick up on
  reconnect (no in-memory-only state).
- Network timeout to RunPod/platforms: exception → `failed` + backoff +
  same-intent retry (no duplicate render/publish).
- DB reconnect: services use short sessions per operation; no long-lived
  transactions held across network calls.
