# FootballPulse — Creator-OS Pulse (Zoza Client) ✅

Creator-OS pulse: intelligence → packages → **Zoza Video Factory** → publishing
→ analytics → revenue → learning. This pulse never renders video locally.

## Run
```bash
pip install -r requirements.txt   # or: pip install -e ".[dev]"
cp .env.example .env              # set ZOZA_DIR, FOOTBALLPULSE_SHARED_BUS=1
docker compose up --build         # api + worker + postgres + redis
# or local:
uvicorn app.main:app --reload
python -m app.queue.worker
alembic upgrade head
pytest -q
```

## Endpoints
- `GET /api/v1/health/live` — liveness
- `GET /api/v1/health/ready` — readiness (postgres + redis)
- `GET /api/v1/agents` — agent roster (20: 12 canonical + intel/decision/content/zoza)
- `GET /api/v1/agents/{name}/health`
- `POST /api/v1/agents/{name}/run`
- `POST /api/v1/agents/tasks` + `GET /api/v1/agents/tasks/{id}` + `POST /api/v1/agents/tasks/{id}/execute`

## Phase 2 — Football Intelligence Layer ✅
- `GET /api/v1/news/` · `/top` · `/breaking`
- `GET /api/v1/matches/analysis` · `/analysis/{id}`
- `GET /api/v1/transfers/` · `/top-rumors` · `/confirmed`
- `GET /api/v1/campaigns/` · `/top` · `/active`
- Intel queues: `fp:queue:news`, `fp:queue:match_analysis`, `fp:queue:transfer`, `fp:queue:campaign`

## Phase 3 — Decision Platform ✅
- `GET /api/v1/predictions/` · `/top` (pending) · `/metrics` (accuracy, Brier)
- `GET /api/v1/opportunities/` · `/top` · `/high-priority`
- `GET /api/v1/executive/decisions` · `/summary` (tiers, conversion rate)
- Decision queues: `fp:queue:prediction`, `fp:queue:executive`, `fp:queue:opportunity`

## Phase 4 — Content Pipeline ✅
- `GET /api/v1/research/` · `/by-topic`
- `GET /api/v1/scripts/` · `/approved` (quality gate ≥ 0.70)
- `GET /api/v1/seo/` · `/top`
- `GET /api/v1/thumbnails/` · `/top` (concepts for Zoza briefs)
- `GET /api/v1/regions/` · `/top` · `/by-tier/{1,2,3}`
- `GET /api/v1/packages/` · `/ready` · `/{id}` (bundle + publishing strategy)
- Content queues: `fp:queue:research`, `fp:queue:planner`, `fp:queue:script`, `fp:queue:seo`, `fp:queue:thumbnail`, `fp:queue:region`, `fp:queue:packaging`

## Zoza Factory Integration (replaces Phase 5 local video stack) ✅
- `POST /api/v1/zoza/request` (submit package) · `GET /api/v1/zoza/status/{id}`
- `GET /api/v1/zoza/exports` · `POST /api/v1/zoza/retry/{id}` · `GET /api/v1/zoza/factory`
- Queue: `fp:queue:zoza` → `zoza_dispatcher` agent
- Events published: `VIDEO_REQUESTED` · subscribed: `VIDEO_RENDER_STARTED/FINISHED`, `VIDEO_EXPORTED`
- DB: `zoza_requests`, `zoza_exports`, `factory_status` (Phase 5 render tables deprecated, preserved)
- 193 tests passing (`pytest -q`)
