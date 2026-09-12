# Zoza Factory Architecture

```
┌─────────────┐  Contract V2   ┌──────────────────────────────────┐
│ MusicPulse  │──request──────▶│          zoza-factory            │
│ FootballPulse│  goal/style/  │                                  │
│ (WHAT)      │  length/mode/ │  reality_production_director     │
└─────────────┘  sources/     │    │ hierarchy: footage>photo>    │
       ▲         evidence/     │    │ licensed>public-domain>AI   │
       │         voice/aud/    │    ▼                            │
       │         priority      │  rights_validation ──▶ BLOCKED?  │
       │                       │    │ CLEARED/RESTRICTED/         │
       │  export.json          │    │ UNKNOWN(flagged)/BLOCKED    │
       │  (rendered,           │    ▼                            │
       │   never published)    │  reality_assets ──▶ acquire +   │
       └──────────────────────│    │ catalog + seed archives     │
                               │    ▼                            │
                               │  voice_intelligence (5 profiles)│
                               │    ▼                            │
                               │  timeline_builder ──▶ scenes +  │
                               │    │ SRT, total == narration    │
                               │    ▼                            │
                               │  production_strategy ──▶        │
                               │    │ explainable plan + ratios  │
                               │    ▼                            │
                               │  renderer: assemble → subs →    │
                               │  voice → render → export.json   │
                               │  (NO publishing code paths)     │
                               └───┬──────────────┬──────────────┘
                                   │ events       │ heartbeat
                                   ▼              ▼
                          shared/event_bus  shared/orchestrator
                          VIDEO_REQUESTED   register_factory
                          VIDEO_RENDER_*    + health/capacity
                          VIDEO_EXPORTED
```

## Request lifecycle

`created → planned → acquiring → assembling → rendering → exported | failed`
(`app/services/pipeline.py`). Planning is pure (director over candidates);
execution writes `output/<request_id>/{assembly.json,subtitles.srt,video.mp4,thumbnail.jpg,export.json}`.

## Production modes

- **REALITY_ONLY** — real assets only; AI never injected, even on gaps; UNKNOWN-rights excluded.
- **REALITY_FIRST** — hierarchy order; AI fills gaps only when `ai_generation_allowed` is true.
- **HYBRID** — AI always permitted; real+AI mix.
- **AI_CREATIVE** — AI always permitted; AI candidates ranked first; fiction allowed.

Effective gate (`director.effective_ai_allowed`): ONLY→False, HYBRID/CREATIVE→True,
FIRST→flag. AI fallback placeholder is synthesized only when allowed AND
zero usable real assets exist.

## Module map

| Module | Decides | Never touches |
|---|---|---|
| `reality_production_director` | best strategy, orchestration | publishing, revenue |
| `production_strategy` | asset/voice/timeline/render plan + ratios | I/O, business |
| `reality_assets` | candidates, trust, catalog | rights verdicts |
| `rights_validation` | CLEARED/RESTRICTED/UNKNOWN/BLOCKED | asset sourcing |
| `voice_intelligence` | profile/tone/pacing/emotion | rendering |
| `timeline_builder` | scenes/SRT, exact duration match | voice selection |
| `renderer` | assembly/render/export files | publishing (absent + tested) |

## Boundary guarantees (tested)

1. Contract V2 has no publish/audience/revenue fields (`test_contract_v2_has_no_business_fields`).
2. Renderer contains no publish/upload/social/revenue code (`test_renderer_has_no_publishing_path`).
3. Every export passes `shared/contracts.py::validate_export` (`test_export_conforms_to_shared_contract`).
4. BLOCKED rights never usable in any mode; UNKNOWN excluded from REALITY_ONLY.
5. Video duration always equals narration length (`matches_narration is True`).
