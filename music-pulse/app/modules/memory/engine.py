"""Business Memory Engine: persistent, searchable decision/outcome memory."""
from __future__ import annotations
from sqlalchemy import or_

from app.core.audit import audit

KINDS = ("decision", "outcome", "success", "failure", "lesson", "market")


def store(db, kind: str, title: str, body: str = "", score: float = 0.0,
          ref_type: str = "", ref_id: str = "", actor: str = "executive"):
    from app.models.phase3 import BusinessMemory
    if kind not in KINDS:
        raise ValueError(f"unknown memory kind: {kind}")
    row = BusinessMemory(kind=kind, title=title, body=body, score=score,
                         ref_type=ref_type, ref_id=str(ref_id))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "memory.stored", "memory", row.id, {"kind": kind})
    return row


def search(db, query: str, kind: str | None = None, limit: int = 10) -> list[dict]:
    """Keyword search over titles/bodies (portable LIKE search, no pg extension needed)."""
    from app.models.phase3 import BusinessMemory
    q = db.query(BusinessMemory)
    if kind:
        q = q.filter(BusinessMemory.kind == kind)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(BusinessMemory.title.like(like), BusinessMemory.body.like(like)))
    rows = q.order_by(BusinessMemory.id.desc()).limit(limit).all()
    return [{"id": r.id, "kind": r.kind, "title": r.title, "body": r.body,
             "score": r.score} for r in rows]


def record_outcome(db, ref_type: str, ref_id: str, success: bool,
                   note: str = "", score: float = 0.0, actor: str = "executive"):
    kind = "success" if success else "failure"
    return store(db, kind, f"{ref_type}:{ref_id} {'succeeded' if success else 'failed'}",
                 note, score, ref_type, ref_id, actor)


def lessons(db, limit: int = 10) -> list[dict]:
    """Top lessons by outcome score — consulted by the Executive Agent."""
    from app.models.phase3 import BusinessMemory
    rows = (db.query(BusinessMemory)
            .filter(BusinessMemory.kind.in_(["lesson", "success", "failure"]))
            .order_by(BusinessMemory.score.desc()).limit(limit).all())
    return [{"id": r.id, "kind": r.kind, "title": r.title, "score": r.score} for r in rows]


def history(db, ref_type: str = "", limit: int = 50) -> list[dict]:
    from app.models.phase3 import BusinessMemory
    q = db.query(BusinessMemory).order_by(BusinessMemory.id.desc())
    if ref_type:
        q = q.filter(BusinessMemory.ref_type == ref_type)
    return [{"id": r.id, "kind": r.kind, "title": r.title,
             "ref": f"{r.ref_type}:{r.ref_id}"} for r in q.limit(limit).all()]
