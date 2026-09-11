"""Label Intelligence Network: majors, independents, emerging labels."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("major", "independent", "emerging")


def upsert_label(db, label: str, kind: str = "independent", signings: int = 0,
                 releases: int = 0, activity: float = 0.0,
                 actor: str = "label_intel"):
    from app.models.phase7 import LabelProfile
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = db.query(LabelProfile).filter(LabelProfile.label == label).first()
    if row is None:
        row = LabelProfile(label=label)
        db.add(row)
    row.kind = kind
    row.signings = signings
    row.releases = releases
    row.activity = activity
    db.commit()
    db.refresh(row)
    audit(db, actor, "label.profiled", "label", row.id, {"label": label})
    return row


def label_report(db, label: str) -> dict:
    from app.models.phase7 import LabelProfile, ArtistProfile
    row = db.query(LabelProfile).filter(LabelProfile.label == label).first()
    if row is None:
        raise ValueError(f"no intelligence on {label}")
    roster = db.query(ArtistProfile).filter(ArtistProfile.label == label).count()
    return {"label": row.label, "kind": row.kind, "signings": row.signings,
            "releases": row.releases, "activity": row.activity, "roster": roster}


def active_labels(db, limit: int = 10) -> list[dict]:
    from app.models.phase7 import LabelProfile
    rows = db.query(LabelProfile).order_by(
        LabelProfile.activity.desc()).limit(limit).all()
    return [{"label": r.label, "kind": r.kind, "activity": r.activity} for r in rows]
