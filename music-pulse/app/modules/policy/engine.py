"""Policy Governance System: replaces HITL approvals with enforcement.

Every publish passes check_content(); blocks are recorded as PolicyEvents
and surfaced in audit. Rules: no politics, hate, misinformation, unverified
rumors, copyright red flags, rate limits, brand safety.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta

from app.core.audit import audit

RULES = ("no_politics", "no_hate", "no_misinformation", "no_rumors",
         "copyright", "rate_limit", "brand_safety")

_PATTERNS: dict[str, list[str]] = {
    "no_politics": ["election", "vote for", "senator", "president", "parliament", "campaign rally"],
    "no_hate": ["hate ", "kill all", "ethnic cleansing", "racial slur"],
    "no_misinformation": ["cure for cancer", "miracle cure", "vaccines cause", "flat earth"],
    "no_rumors": ["unconfirmed rumor", "allegedly died", "secret arrest"],
    "copyright": ["leaked album download", "free mp3 download", "pirated"],
    "brand_safety": ["explicit gore", "porn", "casino hack"],
}

MAX_POSTS_PER_HOUR = 20


def check_content(db, title: str = "", body: str = "",
                  content_ref: str = "", actor: str = "policy") -> dict:
    """Return {allowed: bool, rule: str|None}. Logs a PolicyEvent per call."""
    from app.models.phase2 import Campaign  # noqa: F401 (keeps phase2 in scope)
    from app.models.phase3 import PolicyEvent
    text = f"{title}\n{body}".lower()
    blocked_rule = None
    for rule, patterns in _PATTERNS.items():
        if any(p in text for p in patterns):
            blocked_rule = rule
            break
    if blocked_rule is None and not _within_rate_limit(db):
        blocked_rule = "rate_limit"
    verdict = "block" if blocked_rule else "pass"
    row = PolicyEvent(rule=blocked_rule or "all", verdict=verdict,
                      content_ref=str(content_ref),
                      detail=f"checked {len(text)} chars")
    db.add(row)
    db.commit()
    audit(db, actor, f"policy.{verdict}", "policy_event", row.id,
          {"rule": blocked_rule or "all", "ref": str(content_ref)})
    return {"allowed": blocked_rule is None, "rule": blocked_rule}


def _within_rate_limit(db) -> bool:
    from app.models.models import PublishJob
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    n = db.query(PublishJob).filter(PublishJob.updated_at >= hour_ago).count()
    return n < MAX_POSTS_PER_HOUR


def events(db, verdict: str | None = None, limit: int = 50) -> list[dict]:
    from app.models.phase3 import PolicyEvent
    q = db.query(PolicyEvent).order_by(PolicyEvent.id.desc())
    if verdict:
        q = q.filter(PolicyEvent.verdict == verdict)
    return [{"id": r.id, "rule": r.rule, "verdict": r.verdict,
             "ref": r.content_ref} for r in q.limit(limit).all()]


def is_safe_text(title: str = "", body: str = "") -> bool:
    """Pure helper (no DB) for quick pre-checks."""
    text = f"{title}\n{body}".lower()
    return not any(p in text for pats in _PATTERNS.values() for p in pats)
