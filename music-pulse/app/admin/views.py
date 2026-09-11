"""Mobile-first admin (Jinja2, no build step, responsive)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/admin/templates")


@router.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    from app.modules.analytics.engine import totals, top_topics
    from app.models.models import ContentItem, PublishJob, TrendItem
    ctx = {
        "request": request,
        "totals": totals(db),
        "topics": top_topics(db, 5),
        "content": db.query(ContentItem).order_by(ContentItem.id.desc()).limit(20).all(),
        "jobs": db.query(PublishJob).order_by(PublishJob.id.desc()).limit(20).all(),
        "trends": db.query(TrendItem).order_by(TrendItem.score.desc()).limit(20).all(),
    }
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@router.get("/admin/executive", response_class=HTMLResponse)
def executive_center(request: Request, db: Session = Depends(get_db)):
    """Executive Command Center: global, country, genre, discovery, revenue,
    sponsor and competitor boards (mobile-first)."""
    from app.modules.market_intelligence.engine import COUNTRIES, fastest_growing
    from app.modules.profitability.engine import leaderboard as prof_board
    from app.modules.discovery.engine import weekly_breakout_predictions, watchlist
    from app.modules.revenue.engine import summary as rev_summary, revenue_forecast
    from app.modules.sponsorships.engine import campaign_performance
    from app.modules.competitors.engine import posting_frequency, content_gaps
    ctx = {
        "request": request,
        "countries": COUNTRIES,
        "fastest_artists": fastest_growing(db, "artist", limit=5),
        "fastest_songs": fastest_growing(db, "song", limit=5),
        "genres": prof_board(db, limit=5),
        "breakouts": weekly_breakout_predictions(db, 5),
        "watch": watchlist(db)[:10],
        "revenue": rev_summary(db),
        "forecast": revenue_forecast(db),
        "campaigns": campaign_performance(db, 5),
        "competitors": posting_frequency(db)[:8],
        "gaps": content_gaps(db, limit=8),
    }
    return templates.TemplateResponse(request, "executive.html", ctx)


@router.get("/admin/autonomy", response_class=HTMLResponse)
def autonomy_center(request: Request, db: Session = Depends(get_db)):
    """Executive Command Center v2: strategy, memory, optimizer, opportunities,
    activity feed and decision audit (mobile-first)."""
    from app.modules.executive.engine import latest_strategy, goals
    from app.modules.memory.engine import lessons
    from app.modules.revenue_optimizer.engine import results as opt_results
    from app.modules.allocation.engine import priority_queue
    from app.modules.autonomy.engine import cycles, activity_feed, is_running
    from app.modules.decision.engine import decisions
    ctx = {
        "request": request,
        "running": is_running(),
        "strategy": latest_strategy(db) or {},
        "goals": goals(db)[:10],
        "lessons": lessons(db, 8),
        "optimizations": opt_results(db, 8),
        "opportunities": priority_queue(db, 10),
        "cycles": cycles(db, 10),
        "feed": activity_feed(db, 20),
        "decisions": decisions(db, 10),
    }
    return templates.TemplateResponse(request, "autonomy.html", ctx)


@router.get("/admin/network", response_class=HTMLResponse)
def network_center(request: Request, db: Session = Depends(get_db)):
    """Command Center v3: growth, assets, forecasts, breakouts, monetization,
    execution, network, products (mobile-first)."""
    from app.modules.acquisition.engine import growth_report
    from app.modules.network.engine import nodes, seed_default_network
    from app.modules.assets.engine import valuation_report, performance_report
    from app.modules.prediction.engine import forecast_report
    from app.modules.breakout.engine import watchlist as bo_watch
    from app.modules.monetization.engine import InventoryManager
    from app.modules.revenue_execution.engine import utilization, active_campaigns
    from app.modules.forecasting.engine import latest as fc_latest
    from app.modules.products.engine import performance as prod_perf, totals as prod_totals
    seed_default_network(db)
    ctx = {
        "request": request,
        "growth": growth_report(db),
        "nodes": nodes(db),
        "assets": performance_report(db)[:10],
        "valuation": valuation_report(db),
        "forecasts": forecast_report(db, 30, 8),
        "breakouts": bo_watch(db, limit=8),
        "inventory": InventoryManager.utilization(db),
        "rex": utilization(db),
        "campaigns": active_campaigns(db)[:8],
        "revenue_fc": fc_latest(db, "revenue", "monthly") or {},
        "products": prod_perf(db)[:8],
        "product_totals": prod_totals(db),
    }
    return templates.TemplateResponse(request, "network.html", ctx)


@router.get("/admin/creator", response_class=HTMLResponse)
def creator_center(request: Request, db: Session = Depends(get_db)):
    """Creator-OS dashboards: network overview, pipeline, package/render queues,
    video intelligence, event bus, knowledge (mobile-first)."""
    from app.modules.content_gateway.engine import list_packages
    from app.modules.zoza.engine import render_report, ZozaConnector
    from app.modules.video_opportunities.engine import top_for_zoza
    from app.modules.video_intelligence.engine import best_formats, best_markets
    from app.modules.breakout.engine import watchlist as bo_watch
    try:
        from app.core.shared import event_bus, knowledge, network_orchestrator as orch
        orch.heartbeat("music-pulse", "healthy")
        events = event_bus.history(20)
        network = orch.network_report()
        know = {d: knowledge.search(d, limit=5) for d in
                ("artist", "genre", "trend", "market", "video")}
    except Exception:
        events, network, know = [], {}, {}
    ctx = {"request": request, "zoza": ZozaConnector.ping(),
           "packages": list_packages(db, 15), "jobs": render_report(db)[:15],
           "opportunities": top_for_zoza(db, 8),
           "formats": best_formats(db), "markets": best_markets(db),
           "breakouts": bo_watch(db, limit=8),
           "events": events, "network": network, "knowledge": know}
    return templates.TemplateResponse(request, "creator.html", ctx)


@router.get("/admin/reality", response_class=HTMLResponse)
def reality_center(request: Request, db: Session = Depends(get_db)):
    """Reality Center: sources, media assets, verification, artist/label
    intel, newsroom, documentary + rights (mobile-first)."""
    from app.modules.source_intelligence.engine import recommend_sources
    from app.modules.media_acquisition.engine import asset_report
    from app.modules.verification.engine import verification_log
    from app.modules.artist_intelligence.engine import top_artists
    from app.modules.label_intelligence.engine import active_labels
    from app.modules.newsroom.engine import reports
    from app.modules.documentary.engine import projects
    ctx = {"request": request,
           "sources": recommend_sources(db, limit=10),
           "assets": asset_report(db, limit=10),
           "verifications": verification_log(db, limit=10),
           "artists": top_artists(db, 10),
           "labels": active_labels(db, 10),
           "reports": reports(db, limit=10),
           "docs": projects(db, limit=10)}
    return templates.TemplateResponse(request, "reality.html", ctx)
