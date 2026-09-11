"""Emerging Artist Discovery Engine (Phase 2)."""
from __future__ import annotations

from app.core.audit import audit

CLASSIFICATIONS = ("Emerging", "Rising", "Breakout", "Established")


def classify(followers: int = 0, streams: int = 0, velocity: float = 0.0,
             playlist_count: int = 0) -> str:
    """Threshold-based classification (deterministic, explainable)."""
    breakout = (velocity >= 2.0 and (followers >= 100_000 or streams >= 5_000_000)) \
        or playlist_count >= 50
    if breakout:
        return "Breakout"
    if followers >= 1_000_000 or streams >= 50_000_000:
        return "Established"
    if velocity >= 0.5 or followers >= 10_000 or streams >= 500_000:
        return "Rising"
    return "Emerging"


def upsert_artist(db, artist: str, genre: str = "", country: str = "US",
                  followers: int = 0, streams: int = 0, velocity: float = 0.0,
                  playlist_count: int = 0, actor: str = "system"):
    from app.models.phase2 import ArtistDiscovery
    row = db.query(ArtistDiscovery).filter(
        ArtistDiscovery.artist == artist,
        ArtistDiscovery.country == country.upper()).first()
    if row is None:
        row = ArtistDiscovery(artist=artist, country=country.upper())
        db.add(row)
    row.genre = genre or row.genre
    row.followers = followers
    row.streams = streams
    row.velocity = velocity
    row.playlist_count = playlist_count
    row.classification = classify(followers, streams, velocity, playlist_count)
    db.commit()
    db.refresh(row)
    audit(db, actor, "discovery.upserted", "artist", row.id,
          {"artist": artist, "classification": row.classification})
    return row


def discovery_report(db, classification: str | None = None, limit: int = 20) -> list[dict]:
    from app.models.phase2 import ArtistDiscovery
    q = db.query(ArtistDiscovery).order_by(ArtistDiscovery.velocity.desc())
    if classification:
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown classification: {classification}")
        q = q.filter(ArtistDiscovery.classification == classification)
    return [{"artist": r.artist, "genre": r.genre, "country": r.country,
             "followers": r.followers, "streams": r.streams,
             "velocity": r.velocity, "classification": r.classification}
            for r in q.limit(limit).all()]


def add_watchlist(db, artist_id: int, actor: str = "system"):
    from app.models.phase2 import ArtistDiscovery
    row = db.get(ArtistDiscovery, artist_id)
    if row is None:
        raise ValueError(f"artist {artist_id} not found")
    row.watchlisted = True
    db.commit()
    audit(db, actor, "discovery.watchlisted", "artist", row.id, {"artist": row.artist})
    return row


def watchlist(db) -> list[dict]:
    from app.models.phase2 import ArtistDiscovery
    rows = db.query(ArtistDiscovery).filter(
        ArtistDiscovery.watchlisted.is_(True)).order_by(
        ArtistDiscovery.velocity.desc()).all()
    return [{"id": r.id, "artist": r.artist, "classification": r.classification,
             "velocity": r.velocity} for r in rows]


def weekly_breakout_predictions(db, limit: int = 5) -> list[dict]:
    """Artists most likely to break out: high velocity but not yet Breakout/Established."""
    from app.models.phase2 import ArtistDiscovery
    rows = (db.query(ArtistDiscovery)
            .filter(ArtistDiscovery.classification.in_(["Emerging", "Rising"]))
            .order_by(ArtistDiscovery.velocity.desc()).limit(limit).all())
    return [{"artist": r.artist, "genre": r.genre, "velocity": r.velocity,
             "classification": r.classification,
             "confidence": round(min(r.velocity / 2.0, 1.0), 2)} for r in rows]
