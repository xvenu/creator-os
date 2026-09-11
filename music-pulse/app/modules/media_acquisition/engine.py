"""Media Acquisition Engine: reference-only asset tracking with rights."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("presskit", "photo", "promo", "artwork", "bio", "event_image")


def track_asset(db, title: str, kind: str, ref_url: str = "", source_id: int = 0,
                rights_status: str = "unknown", attribution: str = "",
                actor: str = "media"):
    from app.models.phase7 import MediaAsset
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = MediaAsset(title=title, kind=kind, ref_url=ref_url, source_id=source_id,
                     rights_status=rights_status, attribution=attribution)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "media.tracked", "asset", row.id, {"title": title})
    return row


def asset_report(db, kind: str | None = None, limit: int = 20) -> list[dict]:
    from app.models.phase7 import MediaAsset
    q = db.query(MediaAsset).order_by(MediaAsset.id.desc())
    if kind:
        q = q.filter(MediaAsset.kind == kind)
    return [{"id": r.id, "title": r.title, "kind": r.kind, "ref": r.ref_url,
             "rights": r.rights_status, "attribution": r.attribution}
            for r in q.limit(limit).all()]
