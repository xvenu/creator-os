# Zoza Factory Audit Report (pre-build, read-only)

No live `~/Zoza_anime` checkout exists on this machine. This audit is
reconstructed from the pulse-side integration surface — the only contract
the factory ever exposed:

- `creator-os/ZOZA_AUDIT.md` (publisher, review flow, job states)
- `music-pulse/app/modules/zoza/engine.py` (`idea_engine.generate_job_from_idea`, `jobs/*.json` polling)
- `football-pulse/app/modules/zoza_client/` (file-queue client, package → job JSON)
- `shared/contracts.py` (export contract: factory output is `rendered`, never published)

## 1. Rendering pipeline

`idea → plan → audio/music → render → assemble → thumbnails → export`
(ZOZA_AUDIT prescription §1). Factory states observed via `jobs/*.json`:
`QUEUED → PLANNED → AUDIO_READY → ASSETS_GENERATING → ASSETS_READY →
ASSEMBLING → RENDERED → AWAITING_REVIEW → APPROVED → PUBLISHING →
DELIVERED | FAILED`. Pulse maps everything between `PLANNED` and
`PUBLISHING` to a single `rendering` bucket — the factory's internal
render stages were opaque to callers.

## 2. Voice pipeline

Single string field: `voiceover_script` + `voice_style` (football
`package.to_zoza_job` defaults to `"energetic"`; voice_id override only).
No profile selection, no tone/pacing/emotion matching, no audience
awareness. **Hardcoded path**: one style string, caller-supplied or default.

## 3. Asset acquisition pipeline

State `ASSETS_GENERATING → ASSETS_READY` implies generation, with no
reality alternative anywhere in the contract: no source/evidence fields,
no license/rights fields, no trust scoring. **Hardcoded path**: every
visual is generated; real footage/photos are inexpressible.

## 4. Subtitle pipeline

No subtitle artifact in the job schema or export contract. Football
`_split_scenes` does naive sentence chunking (ceil-division into ≤8
scenes) with no duration model. **Hardcoded path**: scene count heuristic,
no narration↔visual sync, no timing guarantees.

## 5. Assembly pipeline

`ASSEMBLING` is a black box. No timeline model, no pacing inputs, no gap
detection. Video length vs narration length never validated.

## 6. Export pipeline

`output/<job_id>/export.json` + video/thumbnail files, validated
pulse-side against `shared/contracts.py::validate_export`
(`job_id/status/video_path/thumbnail_path/metadata`, `status == rendered`).
Phase 8 redefined `DELIVERED` as "deliverables exported, never published".

## 7. Queue system

File queue: one JSON document per job in `jobs/`. MusicPulse dispatches by
importing Zoza's `idea_engine` in-process; football-pulse writes job JSON
directly (idempotent on `job_id`). No priority handling factory-side
(pulse computes priority), no capacity reporting, no backpressure.

## 8. State machine

Factory-owned states (11, see §1) vs pulse-observed states
(`created/queued/rendering/rendered/published/failed` music,
`created/submitted/queued/rendering/rendered/exported/failed` football).
`PUBLISHING`/`DELIVERED` were publish-flavored states leaking a
non-factory concern (publishing) into the factory — removed by Phase 8.

## 9. Provider architecture

No provider abstraction existed: one TTS path, one generation path, one
review path (`telegram_bot.py` owner review → ship), four hardcoded
uploaders (`publisher.py`: YouTube/TikTok/Instagram/Facebook). The
refactor prescription isolates all of that behind the export interface.

## Hardcoded paths identified (what the new factory fixes)

| # | Hardcoded path | Location | Fix in zoza-factory |
|---|---|---|---|
| 1 | Single AI entry `generate_job_from_idea(idea)` — no production-mode selection | music `zoza/engine.py::_plan_in_zoza` | Contract V2 `production_mode` + Reality Production Director |
| 2 | All visuals generated (`ASSETS_GENERATING`, no source fields) | factory states / job schema | `reality_assets/` + hierarchy (real → AI last) |
| 3 | One voice style string, default `"energetic"` | football `package.to_zoza_job` | `voice_intelligence/` (5 profiles) |
| 4 | Naive scene split, no timing model | football `package._split_scenes` | `timeline_builder/` (word-weighted, exact total) |
| 5 | No rights/license representation at all | entire contract | `rights_validation/` (CLEARED/RESTRICTED/UNKNOWN/BLOCKED) |
| 6 | Publish states + uploaders inside factory | `publisher.py`, `telegram_bot.py` | No publishing code paths, by construction + test |

## Dependency map (before modifications)

```
MusicPulse ──idea_engine.generate_job_from_idea()──▶ Zoza_anime (external, absent)
     │  polls jobs/*.json (11 states)                    │
     │  VIDEO_REQUESTED / PACKAGE_SENT                   │  RENDERED..DELIVERED
     ▼                                                   ▼
shared/event_bus ◀── VIDEO_RENDER_* / VIDEO_EXPORTED ── mark_exported()
shared/contracts.py::validate_export (enforcement point)

FootballPulse ──job JSON write──▶ <ZOZA_DIR>/jobs/ ──▶ (same factory)
     │  DETAIL: publish_targets=[] (never publish)       │
     ▼                                                   ▼
fp:queue:zoza → zoza_dispatcher → collect_export() → contract check
```
