# Zoza Video Factory — publishing-surface audit (read-only, no code changed)

Source: `~/Zoza_anime` (live system, pm2-managed — do NOT modify in place).

## Publishing-related components (to isolate behind the export interface)

| Component | File | Responsibility today |
|---|---|---|
| `ChannelUploader` protocol + `YouTubeUploader` | `publisher.py:21,30` | YouTube upload |
| `TikTokUploader` | `publisher.py:48` | TikTok upload |
| `InstagramUploader` | `publisher.py:64` | Instagram upload |
| `FacebookUploader` | `publisher.py:80` | Facebook upload |
| `publish(job, video_path)` | `publisher.py:101` | multi-channel fan-out |
| Review/publish flow | `telegram_bot.py` | owner review → ship |
| `PUBLISHING` / `DELIVERED` states | `core/job_schema.py`, `job_queue.py` | publish tracking |

Analytics/audience/revenue tracking: none found in Zoza (no such modules) —
nothing to migrate there; Pulses own these greenfield.

## Refactor prescription (for Zoza maintainers, not applied here)

1. Keep: idea → plan → audio/music → render → assemble → thumbnails → export.
2. Replace `publish()` call sites with export-manifest write
   (`output/<job_id>/export.json` conforming to `shared/contracts.py::ZozaExport`).
3. Emit render lifecycle events to the Creator-OS event bus instead of
   driving Telegram review directly (review becomes a Pulse concern).
4. `DELIVERED` is redefined as "deliverables exported", never "published".

## Enforcement from the Pulse side (applied)

- `app/modules/zoza/engine.py::mark_exported` treats Zoza `DELIVERED` as
  **exported**: builds a `PublishableAsset`, stores `ExportedAsset`.
- `PublishTracker.record_publish` retained for backward compat but Zoza-side
  publish states are observed-only; canonical publishing happens in
  `app/modules/distribution/` (Pulse-owned).
- No Zoza code was read for writing, only for state mapping; no Zoza file modified.
