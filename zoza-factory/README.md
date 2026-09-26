# Zoza Factory — universal video factory for Creator-OS

**Pulse decides WHAT. Zoza decides HOW.**

ANY pulse — music, football, anime, movie, ads, or pulses that do not
exist yet — sends a production *request* (goal, style, length, urgency,
production mode, `content_type`, sources, evidence, voice profile,
audience, priority). Zoza Factory chooses assets, voice, pacing,
timeline, builds the video, and exports a contract-validated package.

Content families: `video` (generic/real), `anime` (stylized episode),
`movie` (long-form, three acts), `ad` (hook-body-CTA spot), `ai_film`
(fully synthetic). Real vs AI is orthogonal via production mode
(`REALITY_ONLY` / `REALITY_FIRST` / `HYBRID` / `AI_CREATIVE`) — AI is
always the last option, `BLOCKED` rights never usable.

Zoza Factory is **not** a publisher, analytics system, revenue system, or
Telegram system. It never publishes, never owns audience, never owns revenue,
never makes business decisions. Only production decisions.

## Run

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
pytest -q
docker compose up --build
```

## Production modes

| Mode | Meaning |
|---|---|
| `REALITY_ONLY` | Real videos/photos only. No AI generation, ever. |
| `REALITY_FIRST` | Prefer real assets; AI only to fill gaps when allowed. |
| `HYBRID` | Mix real and AI assets. |
| `AI_CREATIVE` | AI generation allowed; fictional content allowed. |

Decision hierarchy (AI is always last): real footage → real photos →
licensed assets → public-domain assets → AI-generated assets.

## Factory Contract V2 (`POST /api/v1/requests`)

```json
{
  "request_id": "",
  "pulse": "any-pulse-name (no allow-list)",
  "goal": "",
  "style": "",
  "length_seconds": 0,
  "urgency": "normal",
  "production_mode": "REALITY_FIRST",
  "ai_generation_allowed": false,
  "content_type": "video | anime | movie | ad | ai_film",
  "format_variant": "short | episode | feature | spot",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "language": "en",
  "narration": "",
  "brand_context": "",
  "call_to_action": "",
  "sources": [],
  "evidence": [],
  "voice_profile": "",
  "target_audience": "",
  "priority": 0
}
```

Request states: `created → planned → acquiring → assembling → rendering → exported | failed`.

## Endpoints

- `GET /health/live`, `GET /health/ready`
- `POST /api/v1/requests`, `GET /api/v1/requests`, `GET /api/v1/requests/{id}`
- `POST /api/v1/requests/{id}/plan`, `POST /api/v1/requests/{id}/execute`
- `GET /api/v1/exports/{request_id}`
- `GET /api/v1/capabilities`, `GET /api/v1/content-types`
- `POST /api/v1/pulses/register` — any pulse name accepted, no allow-list
- `GET /api/v1/assets/catalog`, `POST /api/v1/assets/acquire`
- `POST /api/v1/rights/validate`
- `POST /api/v1/voice/match`
- `POST /api/v1/timeline/build`
- `GET /api/v1/capacity`

## Modules (`app/modules/`)

- `content_types/` — video/anime/movie/ad/ai_film registry (structure, voice default, render profile)
- `ai_generation/` — synthetic gap-fill prompts + provider abstraction (pure, no network)
- `reality_production_director/` — universal director: rights → assets → voice → timeline → strategy
- `production_strategy/` — asset/voice/timeline/render strategy, explainable plan
- `reality_assets/` — real asset acquisition (official/press/documentary/archives)
- `rights_validation/` — CLEARED / RESTRICTED / UNKNOWN / BLOCKED
- `voice_intelligence/` — documentary / breaking-news / sports-analysis / artist-biography / historical-story
- `timeline_builder/` — visuals ↔ narration sync; video length == narration length
- `renderer/` — assembly, subtitles, voice, rendering, exports. No publishing.

## Creator-OS integration

Registers with shared event bus (`VIDEO_RENDER_STARTED/FINISHED`, `VIDEO_EXPORTED`),
orchestrator (`register_factory` + heartbeats), notifications (fail-open), and
validates every export against `shared/contracts.py::validate_export`.
