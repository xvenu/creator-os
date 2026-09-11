"""Phase 2 API: markets, discovery, profitability, revenue, sponsors, competitors.

All endpoints appear in FastAPI OpenAPI docs (/docs, /openapi.json).
Mutating endpoints write audit logs via the engines.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import audit

router = APIRouter(tags=["phase2"])


# ---------- Market intelligence ----------
class CountryTrendIn(BaseModel):
    country: str
    title: str
    artist: str = ""
    source: str = ""
    rank: int = 0
    score: float = 0.0
    genre: str = ""


@router.post("/markets/record", summary="Record a country trend snapshot")
def markets_record(payload: CountryTrendIn, db: Session = Depends(get_db)):
    from app.modules.market_intelligence.engine import record_country_trend
    row = record_country_trend(db, actor="api", **payload.model_dump())
    return {"id": row.id}


@router.get("/markets/rankings", summary="Independent rankings per country")
def markets_rankings(country: str, limit: int = 20, db: Session = Depends(get_db)):
    from app.modules.market_intelligence.engine import country_rankings
    return {"country": country.upper(), "rankings": country_rankings(db, country, limit)}


@router.get("/markets/fastest", summary="Fastest growing artists/songs/genres")
def markets_fastest(kind: str = "artist", country: str | None = None,
                    limit: int = 10, db: Session = Depends(get_db)):
    from app.modules.market_intelligence.engine import fastest_growing
    return {"fastest": fastest_growing(db, kind, country, limit)}


@router.get("/markets/compare", summary="Cross-country trend comparison")
def markets_compare(title: str = "", artist: str = "", db: Session = Depends(get_db)):
    from app.modules.market_intelligence.engine import cross_country_compare
    return {"comparison": cross_country_compare(db, title, artist)}


@router.get("/markets/migration", summary="Cross-border trend movement")
def markets_migration(db: Session = Depends(get_db)):
    from app.modules.market_intelligence.engine import trend_migration
    return {"migration": trend_migration(db)}


# ---------- Timezone ----------
@router.get("/timezone/best", summary="Best posting times for a country")
def tz_best(country: str = "US", db: Session = Depends(get_db)):
    from app.modules.timezone.engine import best_posting_times
    return {"country": country.upper(), "times": best_posting_times(country, db=db)}


@router.get("/timezone/heatmap", summary="Audience activity heatmap")
def tz_heatmap(country: str = "US", db: Session = Depends(get_db)):
    from app.modules.timezone.engine import heatmap
    return {"country": country.upper(), "heatmap": heatmap(db, country)}


@router.post("/timezone/reschedule/{job_id}", summary="Auto-reschedule a publish job")
def tz_reschedule(job_id: int, country: str = "US", db: Session = Depends(get_db)):
    from app.modules.timezone.engine import auto_reschedule
    job = auto_reschedule(db, job_id, country, actor="api")
    return {"job_id": job.id, "scheduled_at": str(job.scheduled_at)}


# ---------- Profitability ----------
class GenreAnalyticIn(BaseModel):
    genre: str
    country: str = "US"
    views: int = 0
    engagement: int = 0
    posts: int = 0
    retention: float = 0.0
    sponsorship_score: float = 0.0


@router.post("/profitability/record", summary="Record genre analytics")
def prof_record(payload: GenreAnalyticIn, db: Session = Depends(get_db)):
    from app.modules.profitability.engine import record_genre_analytic
    row = record_genre_analytic(db, actor="api", **payload.model_dump())
    return {"id": row.id}


@router.get("/profitability", summary="Genre profitability score")
def prof_score(genre: str, country: str | None = None, db: Session = Depends(get_db)):
    from app.modules.profitability.engine import profitability_score, revenue_opportunity
    return {"profitability": profitability_score(db, genre, country),
            "opportunity": revenue_opportunity(db, genre, country)}


@router.get("/profitability/leaderboard", summary="Genre profitability leaderboard")
def prof_board(country: str | None = None, db: Session = Depends(get_db)):
    from app.modules.profitability.engine import leaderboard
    return {"leaderboard": leaderboard(db, country)}


# ---------- Discovery ----------
class ArtistIn(BaseModel):
    artist: str
    genre: str = ""
    country: str = "US"
    followers: int = 0
    streams: int = 0
    velocity: float = 0.0
    playlist_count: int = 0


@router.post("/discovery/artists", summary="Upsert artist discovery signal")
def disc_upsert(payload: ArtistIn, db: Session = Depends(get_db)):
    from app.modules.discovery.engine import upsert_artist
    row = upsert_artist(db, actor="api", **payload.model_dump())
    return {"id": row.id, "classification": row.classification}


@router.get("/discovery", summary="Discovery reports")
def disc_report(classification: str | None = None, db: Session = Depends(get_db)):
    from app.modules.discovery.engine import discovery_report
    return {"artists": discovery_report(db, classification)}


@router.post("/discovery/watchlist/{artist_id}", summary="Add artist to watchlist")
def disc_watch(artist_id: int, db: Session = Depends(get_db)):
    from app.modules.discovery.engine import add_watchlist
    row = add_watchlist(db, artist_id, actor="api")
    return {"id": row.id, "watchlisted": row.watchlisted}


@router.get("/discovery/breakout", summary="Weekly breakout predictions")
def disc_breakout(db: Session = Depends(get_db)):
    from app.modules.discovery.engine import weekly_breakout_predictions
    return {"predictions": weekly_breakout_predictions(db)}


# ---------- Sponsors ----------
class SponsorIn(BaseModel):
    name: str
    contact: str = ""
    tier: str = "standard"


class CampaignIn(BaseModel):
    sponsor_id: int
    name: str
    package: str
    country: str = "US"
    genre: str = ""
    budget: float = 0.0


@router.post("/sponsors", summary="Create sponsor")
def spon_create(payload: SponsorIn, db: Session = Depends(get_db)):
    from app.modules.sponsorships.engine import create_sponsor
    return {"id": create_sponsor(db, actor="api", **payload.model_dump()).id}


@router.get("/sponsors", summary="List sponsors with revenue/ROI")
def spon_list(db: Session = Depends(get_db)):
    from app.models.phase2 import Sponsor
    from app.modules.sponsorships.engine import sponsor_revenue
    return {"sponsors": [
        {"id": s.id, "name": s.name, "tier": s.tier, **sponsor_revenue(db, s.id)}
        for s in db.query(Sponsor).all()]}


@router.post("/sponsors/campaigns", summary="Create campaign")
def camp_create(payload: CampaignIn, db: Session = Depends(get_db)):
    from app.modules.sponsorships.engine import create_campaign
    return {"id": create_campaign(db, actor="api", **payload.model_dump()).id}


@router.post("/sponsors/campaigns/{cid}/revenue", summary="Attribute revenue to campaign")
def camp_revenue(cid: int, amount: float, db: Session = Depends(get_db)):
    from app.modules.sponsorships.engine import record_campaign_revenue
    row = record_campaign_revenue(db, cid, amount, actor="api")
    return {"id": row.id, "revenue": row.revenue}


@router.get("/sponsors/performance", summary="Campaign performance + ROI")
def spon_perf(db: Session = Depends(get_db)):
    from app.modules.sponsorships.engine import campaign_performance
    return {"performance": campaign_performance(db)}


# ---------- Revenue ----------
class RevenueIn(BaseModel):
    source_type: str
    amount: float
    sponsor_id: int = 0
    campaign_id: int = 0
    country: str = "US"
    genre: str = ""
    platform: str = ""


@router.post("/revenue", summary="Record revenue")
def rev_record(payload: RevenueIn, db: Session = Depends(get_db)):
    from app.modules.revenue.engine import record_revenue
    return {"id": record_revenue(db, actor="api", **payload.model_dump()).id}


@router.get("/revenue/summary", summary="Revenue dashboard data")
def rev_summary(db: Session = Depends(get_db)):
    from app.modules.revenue.engine import summary
    return summary(db)


@router.get("/revenue/forecast", summary="Revenue projections")
def rev_forecast(db: Session = Depends(get_db)):
    from app.modules.revenue.engine import revenue_forecast, revenue_trend
    return {"trend": revenue_trend(db), "forecast": revenue_forecast(db)}


# ---------- Competitors ----------
class CompetitorIn(BaseModel):
    competitor: str
    platform: str = ""
    post_count: int = 0
    formats: dict = {}
    engagement_est: int = 0
    topics: list = []


@router.post("/competitors", summary="Record competitor snapshot")
def comp_record(payload: CompetitorIn, db: Session = Depends(get_db)):
    from app.modules.competitors.engine import record_competitor
    return {"id": record_competitor(db, actor="api", **payload.model_dump()).id}


@router.get("/competitors/frequency", summary="Competitor posting frequency")
def comp_freq(db: Session = Depends(get_db)):
    from app.modules.competitors.engine import posting_frequency
    return {"frequency": posting_frequency(db)}


@router.get("/competitors/gaps", summary="Content gap opportunities")
def comp_gaps(db: Session = Depends(get_db)):
    from app.modules.competitors.engine import content_gaps, weakness_report, trend_opportunities
    audit(db, "api", "competitors.gaps.viewed", "competitor", "", {})
    return {"gaps": content_gaps(db), "weaknesses": weakness_report(db),
            "opportunities": trend_opportunities(db)}
