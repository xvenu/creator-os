# Capacity Report

`GET /api/v1/capacity` exposes:

| Field | Source |
|---|---|
| `active_jobs` | requests in planned/acquiring/assembling/rendering |
| `queued_jobs` | requests in created |
| `average_render_time` | mean `render_seconds` over rendered requests |
| `average_export_time` | mean `export_seconds` over exported requests |
| `provider_availability` | `renderer.PROVIDERS` (render/voice/assets, name+available) |
| `asset_availability` | catalog `{total, by_kind}` |

Plus `exported_jobs` / `failed_jobs` counters. Factory heartbeats to the
shared orchestrator as kind=`factory` with capabilities
`[REALITY_ONLY, REALITY_FIRST, HYBRID, AI_CREATIVE, voice, timeline, render, export]`.

## Snapshot (post-test-run, live verified)

- Providers: `simulated-1080p` / `simulated-tts` / `factory-catalog` — all available.
- Catalog: 4 seeded assets (1 real_footage, 2 real_photo, 1 public_domain).
- Averages populate as jobs export (simulated render ≈ ms).
- Orchestrator shows `zoza-factory: healthy`; registry lists it as kind `factory`.

## Scaling notes

- Real render/voice providers plug in behind `renderer.PROVIDERS` + `provider_availability` without pipeline changes.
- `urgency` (low/normal/high/breaking) is carried on the request for future prioritized scheduling; current worker drains `created` oldest-first.
