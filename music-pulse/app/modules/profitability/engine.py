"""Genre Profitability Engine (Phase 2)."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func

from app.core.audit import audit

GENRES = ("Hip-Hop", "Pop", "R&B", "Country", "EDM", "Latin", "Rock",
          "Afrobeats", "K-Pop", "Indie")

WEIGHTS = {"engagement_rate": 0.30, "growth": 0.25, "sponsorship": 0.20,
           "frequency": 0.15, "retention": 0.10}


def _check_genre(genre: str) -> str:
    if genre not in GENRES:
        raise ValueError(f"unsupported genre: {genre} (use {GENRES})")
    return genre


def record_genre_analytic(db, genre: str, country: str = "US", views: int = 0,
                          engagement: int = 0, posts: int = 0, retention: float = 0.0,
                          sponsorship_score: float = 0.0, actor: str = "system"):
    from app.models.phase2 import GenreAnalytic
    _check_genre(genre)
    row = GenreAnalytic(genre=genre, country=country.upper(), views=views,
                        engagement=engagement, posts=posts, retention=retention,
                        sponsorship_score=sponsorship_score)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "profitability.recorded", "genre_analytic", row.id,
          {"genre": genre, "country": country})
    return row


def _genre_totals(db, genre: str, country: str | None = None) -> dict:
    from app.models.phase2 import GenreAnalytic
    q = db.query(func.coalesce(func.sum(GenreAnalytic.views), 0),
                 func.coalesce(func.sum(GenreAnalytic.engagement), 0),
                 func.coalesce(func.sum(GenreAnalytic.posts), 0),
                 func.coalesce(func.avg(GenreAnalytic.retention), 0.0),
                 func.coalesce(func.avg(GenreAnalytic.sponsorship_score), 0.0))
    q = q.filter(GenreAnalytic.genre == genre)
    if country:
        q = q.filter(GenreAnalytic.country == country.upper())
    v, e, p, r, s = q.one()
    return {"views": int(v), "engagement": int(e), "posts": int(p),
            "retention": float(r or 0.0), "sponsorship": float(s or 0.0)}


def profitability_score(db, genre: str, country: str | None = None) -> dict:
    """0-100 profitability score + component breakdown."""
    from app.models.phase2 import GenreAnalytic
    _check_genre(genre)
    t = _genre_totals(db, genre, country)
    eng_rate = (t["engagement"] / t["views"]) if t["views"] else 0.0
    # growth: recent week views vs prior week views
    now = datetime.utcnow()
    q = db.query(func.coalesce(func.sum(GenreAnalytic.views), 0)).filter(
        GenreAnalytic.genre == genre)
    if country:
        q = q.filter(GenreAnalytic.country == country.upper())
    recent = float(q.filter(GenreAnalytic.recorded_at >= now - timedelta(days=7)).scalar() or 0)
    prior = float(db.query(func.coalesce(func.sum(GenreAnalytic.views), 0)).filter(
        GenreAnalytic.genre == genre,
        GenreAnalytic.recorded_at >= now - timedelta(days=14),
        GenreAnalytic.recorded_at < now - timedelta(days=7)).scalar() or 0)
    growth = ((recent - prior) / prior) if prior else (1.0 if recent else 0.0)
    freq = min(t["posts"] / 10.0, 1.0)  # saturates at 10 posts
    comps = {
        "engagement_rate": min(eng_rate * 5, 1.0),       # 20% rate => 1.0
        "growth": max(0.0, min(growth, 2.0)) / 2.0,       # 200% growth => 1.0
        "sponsorship": min(t["sponsorship"] / 100.0, 1.0),
        "frequency": freq,
        "retention": max(0.0, min(t["retention"], 1.0)),
    }
    score = round(sum(comps[k] * w for k, w in WEIGHTS.items()) * 100, 2)
    return {"genre": genre, "country": country or "ALL", "score": score,
            "components": {k: round(v, 3) for k, v in comps.items()}, "totals": t}


def leaderboard(db, country: str | None = None, limit: int = 10) -> list[dict]:
    rows = [profitability_score(db, g, country) for g in GENRES]
    rows.sort(key=lambda d: d["score"], reverse=True)
    return rows[:limit]


def revenue_opportunity(db, genre: str, country: str | None = None) -> dict:
    s = profitability_score(db, genre, country)
    # opportunity scales score by audience size (log) — big + profitable wins
    import math
    audience = math.log10(max(s["totals"]["views"], 10))
    return {"genre": genre, "revenue_opportunity": round(s["score"] * audience, 2),
            "profitability": s["score"]}


def growth_forecast(db, genre: str, weeks: int = 4) -> dict:
    """Naive linear forecast from last 4 weekly view buckets."""
    from app.models.phase2 import GenreAnalytic
    now = datetime.utcnow()
    buckets = []
    for w in range(4):
        lo, hi = now - timedelta(days=7 * (w + 1)), now - timedelta(days=7 * w)
        v = float(db.query(func.coalesce(func.sum(GenreAnalytic.views), 0)).filter(
            GenreAnalytic.genre == genre,
            GenreAnalytic.recorded_at >= lo, GenreAnalytic.recorded_at < hi
        ).scalar() or 0)
        buckets.append(v)
    buckets.reverse()  # oldest -> newest
    slope = (buckets[-1] - buckets[0]) / 3 if len(buckets) == 4 else 0.0
    proj = [round(max(buckets[-1] + slope * (i + 1), 0), 1) for i in range(weeks)]
    return {"genre": genre, "history": buckets, "projection": proj}
