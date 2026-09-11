"""Source Intelligence System: metadata, reliability, recommendations."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("artist", "label", "press", "news", "industry", "event")


def register_source(db, name: str, kind: str, url: str = "",
                    official: bool = False, actor: str = "sources"):
    from app.models.phase7 import Source
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = Source(name=name, kind=kind, url=url, official=official)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "source.registered", "source", row.id, {"name": name})
    return row


def source_history(db, source_id: int) -> list[dict]:
    from app.models.phase7 import SourceScore, EvidenceRecord
    scores = (db.query(SourceScore).filter(SourceScore.source_id == source_id)
              .order_by(SourceScore.id.desc()).limit(10).all())
    uses = db.query(EvidenceRecord).filter(
        EvidenceRecord.source_id == source_id).count()
    return {"scores": [{"trust": s.trust, "at": str(s.recorded_at)} for s in scores],
            "evidence_uses": uses}


def recommend_sources(db, kind: str | None = None, limit: int = 5) -> list[dict]:
    """Top sources by composite trust; official sources first."""
    from app.models.phase7 import Source
    from app.modules.reality.engine import SourceTrustEngine
    q = db.query(Source).order_by(Source.official.desc())
    if kind:
        q = q.filter(Source.kind == kind)
    out = [{"id": r.id, "name": r.name, "kind": r.kind, "official": r.official,
            "trust": SourceTrustEngine.composite(db, r.id)} for r in q.all()]
    out.sort(key=lambda d: (d["official"], d["trust"]), reverse=True)
    return out[:limit]
