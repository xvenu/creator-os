# MusicPulse — autonomous global music media platform

## Quickstart
```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload            # API + mobile-first admin at /admin
rq worker default                        # publisher worker (needs Redis)
python -m app.bot.telegram               # Telegram control bot
pytest                                    # full test coverage per module
```

## Docker
```bash
docker compose up --build
```

## Architecture
- `app/modules/trends` — Spotify / YouTube / Billboard / TikTok providers (pluggable)
- `app/modules/content` — news, profiles, reviews, rankings, shorts (OSS HF model optional, template fallback)
- `app/modules/publisher` — queue + multi-platform + retry with exponential backoff
- `app/modules/analytics` — views / engagement / follower growth / top topics
- `app/modules/learning` — best genres/formats + auto recommendations
- `app/core` — config, Postgres, Redis/RQ, audit logs, plugin registry
- `app/bot` — Telegram control bot (`/trends /generate /stats /recommend`)
- `app/admin` — mobile-first dashboard at `/admin`
- `plugins/` — drop-in providers/publishers (see examples)

## API
- `GET /health`, `GET/POST /api/trends`, `POST /api/content/generate`, `GET /api/content`
- `POST /api/publish/queue`, `POST /api/publish/run`
- `POST /api/analytics/metric`, `GET /api/analytics/summary`
- `GET /api/learning/recommend`, `GET /api/audit`

## Phase 2 — market intelligence & revenue (v0.2.0)
Markets: US, CA, UK, AU, DE (`MARKETS` env). New modules, all with DB models,
API, audit logs, config and tests; Phase 1 untouched:
- `market_intelligence` — per-country rankings, velocity, fastest-growing,
  cross-country compare, migration detection
- `timezone` — ET/CT/MT/PT/UK/AU/DE heatmaps + best times; publisher
  auto-schedules when `delay_minutes=None` (`POST /api/publish/queue` accepts
  `country`; use `delay_minutes: null`)
- `profitability` — 10-genre profitability score, revenue opportunity, forecasts
- `discovery` — Emerging/Rising/Breakout/Established, watchlists, breakout predictions
- `sponsorships` — sponsors, 5 packages, campaigns, ROI
- `revenue` — sponsorship/affiliate/promotion/platform, MRR, by country/genre/platform, forecast
- `competitors` — frequency, content gaps, weakness reports, opportunities
- Admin: `/admin/executive` command center (mobile-first)
- Telegram: `/markets /profitability /discover /revenue /sponsors /competitors` (admin-protected)
- API: 25 endpoints under `/api/v2/*`, OpenAPI at `/docs`
- Migration: `migrations/002_phase2.sql` (auto-applied via `init_db`)

## Phase 3 — autonomous company (v0.3.0)
No HITL required. New modules (DB + API + audit + config + tests; Phases 1-2 intact):
- `executive` — ExecutiveAgent (highest authority), StrategyPlanner
  (daily/weekly/monthly), GoalManager (growth/revenue/audience)
- `memory` — persistent searchable decisions/outcomes/lessons; consulted before decisions
- `allocation` — ranks Trend/Discovery/Profitability/Competitor/Revenue inputs,
  priority queues + market/genre focus directives
- `decision` — explainable auditable choices (Hip-Hop/Pop, US/UK…) + outcome tracking
- `policy` — replaces approvals: politics/hate/misinformation/rumors/copyright/
  rate-limit/brand-safety; **all publishing passes the gate**
- `director` — turns strategy+scores into queued, policy-checked content
- `revenue_optimizer` — MRR/sponsorship/affiliate recommendations
- `warroom` — gaps, weaknesses, attack strategies
- `autonomy` — Observe→…→Learn loop, fault-tolerant, auto-recovery;
  emergency stop + executive override (`AUTONOMY_ENABLED` env)
- Admin: `/admin/autonomy` command center v2 (mobile-first)
- Telegram: `/executive /strategy /memory /opportunities /decisions /autonomy /warroom`
- API: 20 endpoints under `/api/v3/*` (`executive strategy memory opportunities
  decisions autonomy warroom`), OpenAPI at `/docs`
- Migration: `migrations/003_phase3.sql`

## Phase 4 — growth/prediction/monetization network (v0.4.0)
Phases 1–3 untouched. New (DB + API + audit + config + tests):
- `acquisition` — follower/subscriber/traffic trackers, conversion funnels
  (rate/CPA/LTV), growth reports, recommendations, audience forecasts
- `network` — 7-node default network (Global/US/UK/Hip-Hop/Pop/EDM/Country),
  resource/content/growth allocation
- `assets` — traffic/revenue/growth/engagement tracking, valuation, expansion
- `prediction` — artist/song/genre/market forecasts, 7/30/90d, explainable+audited
- `breakout` — viral/breakout scan, watchlists, early alerts, exec recommendations
- `monetization` — SponsorMatcher, PricingEngine, AffiliateOptimizer,
  InventoryManager, CampaignAllocator
- `revenue_execution` — plan/execute revenue actions, utilization, forecasts
- `orchestrator` — overlap/duplication/conflict detection + network plan
- `forecasting` — revenue/growth/market/audience, weekly→annual, risks
- `products` — catalog, sales, retention
- Autonomy: `run_cycle_v4` (11 stages incl. Acquire + Monetize); v3 loop unchanged
- Admin: `/admin/network` command center v3 (mobile-first)
- Telegram: `/growth /predict /breakouts /assets /network /monetize /forecast /products`
- API: 18 endpoints under `/api/v4/*`, OpenAPI at `/docs`
- Migration: `migrations/004_phase4.sql`

## Phase 6 — Creator-OS intelligence brain (v0.6.0)
MusicPulse discovers → Zoza Video Factory (`ZOZA_DIR`, default `~/Zoza_anime`)
creates → Creator-OS coordinates. Phases 1–4 untouched:
- `content_gateway` — 8 package types with full video schema, JSON/API/queue export
- `zoza` — dispatch via Zoza's own `idea_engine` (never copied), render/publish
  trackers, retry/failure handling, autonomous `run_pipeline`
- `video_opportunities` — predicted views/watch/engagement/revenue scoring;
  only top-ranked reach Zoza
- `video_intelligence` — best formats/markets/genres/artists, feeds Executive,
  Prediction, Monetization, Learning
- `formats` — 9 formats auto-decided from live signals + performance reports
- `feedback` — ingest views/watch/revenue/CTR/retention/growth, update brain
- `creator-os/shared/` — `event_bus` (8 events, persistence, replay, poll),
  `orchestrator` (health/workload/network reports), `knowledge` (5 domains)
- Admin: `/admin/creator` network dashboards (mobile-first)
- Telegram: `/zoza /packages /videos /pipeline /events /network /knowledge /feedback`
- API: 21 endpoints under `/api/v6/*`, OpenAPI at `/docs`
- Migration: `migrations/005_phase6.sql`

## Phase 7 — reality-first organization (v0.7.0)
Reality before generation; AI augments, never sources. Phases 1–6 untouched:
- `reality` — discovery/trust/evidence/validation engines + Reality Reports
- `source_intelligence` — metadata, reliability history, recommendations
- `media_acquisition` — reference-only assets (never copied), rights-tracked
- `verification` — verified/unverified/disputed/insufficient; packages stamped
- `artist_intelligence` / `label_intelligence` — profiles, momentum, reports
- `newsroom` — sourced, evidenced, verification-stamped reports
- `documentary` — research packets → evidence-backed Zoza packages
- `rights` — every asset carries license/owner/attribution metadata
- Executive `decide_reality_first`: verified→evidence→memory→models→AI (never reversed)
- Knowledge graphs: artist/label/event/release/source (+neighbors API)
- Admin: `/admin/reality` with 7 centers (mobile-first)
- Telegram: `/reality /sources /assets /verify /artists /labels /newsroom /documentary`
- API: 15 paths under `/api/v7/*`, OpenAPI at `/docs`
- Migration: `migrations/006_phase7.sql`

## Phase 8 — responsibility refactor (v0.8.0)
Pulse owns business (publish/analytics/audience/revenue); Zoza renders only;
Creator-OS coordinates. Phases 1–7 untouched (Zoza_anime itself unmodified):
- `distribution/` — Pulse publishes exports, tracks performance, learns
- `zoza.mark_exported` — DELIVERED treated as exported (contract-validated);
  new render/publish lifecycle events emitted
- `shared/contracts.py` — PublishableAsset + ZozaExport schemas
- `shared/notifications/` — log/webhook/email/telegram channels, 5 event kinds
- `shared/telegram/` — sole Telegram owner (6 commands); pulse bot deprecated
- `app/bot` — deprecated shim, fully functional, never on critical path
- API: 9 endpoints under `/api/v8/*` (creator + distribution)
- Migration: `migrations/007_phase8.sql`; docs: `creator-os/REFACTOR.md`, `ZOZA_AUDIT.md`
