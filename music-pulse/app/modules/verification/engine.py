"""Fact Verification Engine: verified / unverified / disputed / insufficient."""
from __future__ import annotations

from app.core.audit import audit

VERDICTS = ("verified", "unverified", "disputed", "insufficient")
CATEGORIES = ("artist", "release", "concert", "claim", "story")


def verify_claim(db, subject: str, category: str = "claim", actor: str = "verify",
                 evidence_count: int = 0, trusted_hits: int = 0,
                 disputes: int = 0) -> dict:
    from app.models.phase7 import VerificationEvent
    if category not in CATEGORIES:
        raise ValueError(f"category must be {CATEGORIES}")
    if disputes > 0 and evidence_count > 0:
        verdict = "disputed"
    elif trusted_hits >= 2 or evidence_count >= 3:
        verdict = "verified"
    elif evidence_count == 0:
        verdict = "insufficient"
    else:
        verdict = "unverified"
    rationale = (f"{evidence_count} evidence items, {trusted_hits} from trusted "
                 f"sources, {disputes} disputes")
    row = VerificationEvent(subject=subject, category=category,
                            verdict=verdict, rationale=rationale)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, f"verify.{verdict}", "verification", row.id, {"subject": subject[:80]})
    return {"id": row.id, "subject": subject, "verdict": verdict, "rationale": rationale}


def verification_status(db, subject: str) -> str:
    from app.models.phase7 import VerificationEvent
    r = (db.query(VerificationEvent).filter(VerificationEvent.subject == subject)
         .order_by(VerificationEvent.id.desc()).first())
    return r.verdict if r else "unverified"


def verification_log(db, verdict: str | None = None, limit: int = 20) -> list[dict]:
    from app.models.phase7 import VerificationEvent
    q = db.query(VerificationEvent).order_by(VerificationEvent.id.desc())
    if verdict:
        q = q.filter(VerificationEvent.verdict == verdict)
    return [{"id": r.id, "subject": r.subject, "category": r.category,
             "verdict": r.verdict} for r in q.limit(limit).all()]
