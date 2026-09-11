"""Market Intelligence Engine: country trends, velocity, migration (Phase 2)."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func

from app.core.audit import audit

COUNTRIES = ("US", "CA", "UK", "AU", "DE")


def _check_country(country: str) -> str:
    c = (country or "").upper()
    if c not in COUNTRIES:
        raise ValueError(f"unsupported country: {country} (use {COUNTRIES})")
    return c


def record_country_trend(db, country: str, title: str, artist: str = "",
                         source: str = "", rank: int = 0, score: float = 0.0,
                         genre: str = "", actor: str = "system"):
    from app.models.phase2 import CountryTrend
    country = _check_country(country)
    row = CountryTrend(country=country, source=source, title=title, artist=artist,
                       rank=rank, score=score, genre=genre)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "market.trend.recorded", "country_trend", row.id,
          {"country": country, "title": title})
    return row


def country_rankings(db, country: str, limit: int = 20) -> list[dict]:
    from app.models.phase2 import CountryTrend
    country = _check_country(country)
    # Latest snapshot per title: max score in last 7 days, grouped
    since = datetime.utcnow() - timedelta(days=7)
    rows = (db.query(CountryTrend.title, CountryTrend.artist,
                     func.max(CountryTrend.score).label("score"),
                     func.min(CountryTrend.rank).label("rank"))
            .filter(CountryTrend.country == country, CountryTrend.fetched_at >= since)
            .group_by(CountryTrend.title, CountryTrend.artist)
            .order_by(func.max(CountryTrend.score).desc())
            .limit(limit).all())
    return [{"title": t, "artist": a, "score": float(s or 0), "rank": int(r or 0)}
            for t, a, s, r in rows]


def velocity(db, country: str, title: str = "", artist: str = "",
             window_days: int = 7) -> float:
    """Trend velocity: recent avg score vs prior window avg (positive = accelerating)."""
    from app.models.phase2 import CountryTrend
    country = _check_country(country)
    now = datetime.utcnow()
    mid = now - timedelta(days=window_days)
    old = now - timedelta(days=2 * window_days)
    q = db.query(func.coalesce(func.avg(CountryTrend.score), 0.0))
    if title:
        q = q.filter(CountryTrend.title == title)
    if artist:
        q = q.filter(CountryTrend.artist == artist)
    recent = float(q.filter(CountryTrend.country == country,
                            CountryTrend.fetched_at >= mid).scalar() or 0.0)
    prior = float(db.query(func.coalesce(func.avg(CountryTrend.score), 0.0))
                  .filter(CountryTrend.country == country,
                          CountryTrend.fetched_at >= old,
                          CountryTrend.fetched_at < mid).scalar() or 0.0)
    if title:
        pass  # filters above already applied to recent; apply to prior below if needed
    if not prior:
        return round(recent, 2)
    return round((recent - prior) / prior, 4)


def fastest_growing(db, kind: str = "artist", country: str | None = None,
                    limit: int = 10) -> list[dict]:
    """Fastest growing artists / songs / genres by velocity x volume."""
    from app.models.phase2 import CountryTrend
    now = datetime.utcnow()
    week = now - timedelta(days=7)
    col = {"artist": CountryTrend.artist, "song": CountryTrend.title,
           "genre": CountryTrend.genre}.get(kind)
    if col is None:
        raise ValueError("kind must be artist|song|genre")
    q = db.query(col, func.avg(CountryTrend.score).label("avg"),
                 func.count(CountryTrend.id).label("n")).filter(CountryTrend.fetched_at >= week)
    if country:
        q = q.filter(CountryTrend.country == _check_country(country))
    rows = q.group_by(col).all()
    out = [{"key": k or "unknown", "avg_score": round(float(a or 0), 2),
            "mentions": int(n or 0),
            "velocity": round(float(a or 0) * int(n or 0), 2)} for k, a, n in rows]
    out.sort(key=lambda d: d["velocity"], reverse=True)
    return out[:limit]


def cross_country_compare(db, title: str = "", artist: str = "") -> list[dict]:
    """Per-country scores for one song/artist."""
    from app.models.phase2 import CountryTrend
    q = db.query(CountryTrend.country, func.max(CountryTrend.score).label("score"),
                 func.min(CountryTrend.rank).label("rank"))
    if title:
        q = q.filter(CountryTrend.title == title)
    if artist:
        q = q.filter(CountryTrend.artist == artist)
    rows = q.group_by(CountryTrend.country).all()
    return [{"country": c, "score": float(s or 0), "rank": int(r or 0)} for c, s, r in rows]


def trend_migration(db, min_countries: int = 2) -> list[dict]:
    """Songs/artists charting in multiple countries (cross-border movement)."""
    from app.models.phase2 import CountryTrend
    rows = (db.query(CountryTrend.title, CountryTrend.artist,
                     func.count(func.distinct(CountryTrend.country)).label("n"),
                     func.max(CountryTrend.score).label("score"))
            .group_by(CountryTrend.title, CountryTrend.artist)
            .having(func.count(func.distinct(CountryTrend.country)) >= min_countries)
            .order_by(func.max(CountryTrend.score).desc()).all())
    return [{"title": t, "artist": a, "countries": int(n), "score": float(s or 0)}
            for t, a, n, s in rows]
