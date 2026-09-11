"""Music Newsroom Engine: sourced, evidenced, verification-stamped reports."""
from __future__ import annotations
import json

from app.core.audit import audit

KINDS = ("news", "analysis", "market", "release", "event")


def write_report(db, kind: str, title: str, body: str, sources: list | None = None,
                 actor: str = "newsroom") -> dict:
    from app.models.phase7 import NewsroomReport
    from app.modules.verification.engine import verify_claim
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    sources = sources or []
    verdict = verify_claim(db, title, "story", actor,
                           evidence_count=len(sources),
                           trusted_hits=sum(1 for s in sources if s.get("trusted")))
    row = NewsroomReport(kind=kind, title=title, body=body,
                         sources_json=json.dumps(sources),
                         verification=verdict["verdict"])
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "newsroom.published", "report", row.id,
          {"verification": verdict["verdict"]})
    return {"id": row.id, "title": title, "verification": verdict["verdict"],
            "sources": sources}


def reports(db, kind: str | None = None, limit: int = 20) -> list[dict]:
    from app.models.phase7 import NewsroomReport
    q = db.query(NewsroomReport).order_by(NewsroomReport.id.desc())
    if kind:
        q = q.filter(NewsroomReport.kind == kind)
    return [{"id": r.id, "kind": r.kind, "title": r.title,
             "verification": r.verification,
             "sources": json.loads(r.sources_json or "[]")}
            for r in q.limit(limit).all()]
