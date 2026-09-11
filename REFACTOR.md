# Creator-OS Responsibility Refactor — Report

## Dependency map

```
MusicPulse (business: intelligence→publish→growth→revenue)
  │  VIDEO_REQUESTED / PACKAGE_SENT
  ▼
Zoza Video Factory (render only: assets→video→thumbnails→export)
  │  VIDEO_RENDER_STARTED/FINISHED, VIDEO_EXPORTED (PublishableAsset)
  ▼
MusicPulse distribution/ (publishes, tracks, learns)
  │  PUBLISH_STARTED/COMPLETED, REVENUE_RECORDED, alerts
  ▼
Creator-OS (observes: bus, knowledge, orchestrator, notifications, telegram)
```

Zoza_anime internals were audited read-only (see ZOZA_AUDIT.md); zero files modified.
Enforcement is Pulse-side: `mark_exported()` + `shared/contracts.py`.

## Event flow (ownership annotated)

1. `PACKAGE_CREATED` (pulse) → 2. `VIDEO_REQUESTED` (pulse) → 3. `VIDEO_RENDER_STARTED`
   (factory) → 4. `VIDEO_RENDER_FINISHED` (factory) → 5. `VIDEO_EXPORTED` (pulse,
   contract-validated) → 6. `PUBLISH_STARTED` (pulse) → 7. `PUBLISH_COMPLETED`
   (pulse) → 8. `REVENUE_RECORDED` (pulse) → alerts to notification center.

Factory emits render events only. Pulse emits publishing events only.

## Migration report

- `migrations/007_phase8.sql`: `exported_assets`, `notification_events`
  (mirror), `pulse_registrations`. `factory_jobs` intentionally NOT created —
  factory runtime state is Zoza-owned, observed via `jobs/*.json` polling;
  `zoza_jobs` (Phase 6) remains the Pulse-side record.
- Shared runtime state (`notifications.db`, `orchestrator.db` registry,
  `event_bus.db`) is created lazily by the shared layer — no migration step.
- `app/bot/telegram.py`: deprecated (warning on `build_app()`), fully functional.
  Creator-OS agent (`shared/telegram/`) is the sole Telegram owner going forward.

## Independence guarantees (tested)

- Telegram disabled/absent → publishing, decisions, recovery, scheduling unaffected
  (bot was always a separate opt-in process; now deprecated).
- Creator-OS shared layer raising → all Pulse engines fail open (bus/knowledge
  calls wrapped; notification fan-out never raises).
- Zoza unreachable → dispatch stays retryable `queued`; pipeline reports failure
  per-item without aborting; autonomy loops continue.
