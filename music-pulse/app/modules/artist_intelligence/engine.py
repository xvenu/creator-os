"""Artist Intelligence Network: profiles, momentum, coverage, reports."""
from __future__ import annotations

from app.core.audit import audit


def upsert_profile(db, artist: str, label: str = "", genre: str = "",
                   bio_ref: str = "", momentum: float = 0.0,
                   actor: str = "artist_intel"):
    from app.models.phase7 import ArtistProfile
    row = db.query(ArtistProfile).filter(ArtistProfile.artist == artist).first()
    if row is None:
        row = ArtistProfile(artist=artist)
        db.add(row)
    row.label = label or row.label
    row.genre = genre or row.genre
    row.bio_ref = bio_ref or row.bio_ref
    row.momentum = momentum
    try:
        from app.modules.discovery.engine import discovery_report
        row.coverage = sum(1 for r in discovery_report(db, limit=100)
                           if r["artist"] == artist)
    except Exception:
        pass
    db.commit()
    db.refresh(row)
    audit(db, actor, "artist.profiled", "artist", row.id, {"artist": artist})
    return row


def artist_report(db, artist: str) -> dict:
    from app.models.phase7 import ArtistProfile, EvidenceRecord
    row = db.query(ArtistProfile).filter(ArtistProfile.artist == artist).first()
    if row is None:
        raise ValueError(f"no intelligence on {artist}")
    ev = db.query(EvidenceRecord).filter(
        EvidenceRecord.claim.like(f"%{artist[:30]}%")).count()
    return {"artist": row.artist, "label": row.label, "genre": row.genre,
            "momentum": row.momentum, "coverage": row.coverage,
            "evidence_items": ev}


def top_artists(db, limit: int = 10) -> list[dict]:
    from app.models.phase7 import ArtistProfile
    rows = db.query(ArtistProfile).order_by(
        ArtistProfile.momentum.desc()).limit(limit).all()
    return [{"artist": r.artist, "momentum": r.momentum, "label": r.label}
            for r in rows]
