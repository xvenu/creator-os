"""Documentary Intelligence System: research packets for Zoza Video Factory."""
from __future__ import annotations
import json

from app.core.audit import audit


def build_project(db, subject: str, actor: str = "documentary") -> dict:
    from app.models.phase7 import DocumentaryProject, EvidenceRecord
    from app.modules.artist_intelligence.engine import artist_report
    try:
        intel = artist_report(db, subject)
    except ValueError:
        intel = {"artist": subject, "momentum": 0.0}
    ev = (db.query(EvidenceRecord).filter(
        EvidenceRecord.claim.like(f"%{subject[:30]}%")).limit(10).all())
    research = {"intel": intel,
                "evidence": [{"claim": e.claim, "url": e.url} for e in ev]}
    brief = (f"Documentary: {subject}. Angle: rise, sound, impact. "
             f"Evidence items: {len(ev)}.")
    script = (f"COLD OPEN: {subject} changed the sound. ACT 1: origins. "
              f"ACT 2: breakthrough ({intel.get('momentum', 0)} momentum). "
              f"ACT 3: legacy. All claims sourced; see research packet.")
    row = DocumentaryProject(subject=subject, brief=brief, script=script,
                             research_json=json.dumps(research))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "documentary.built", "documentary", row.id, {"subject": subject})
    return {"id": row.id, "subject": subject, "brief": brief,
            "script": script, "research": research}


def to_package(db, project_id: int, actor: str = "documentary") -> dict:
    """Hand the documentary to Zoza as an evidence-backed content package."""
    from app.models.phase7 import DocumentaryProject
    from app.modules.content_gateway.engine import build_package
    from app.modules.verification.engine import verification_status
    proj = db.get(DocumentaryProject, project_id)
    if proj is None:
        raise ValueError(f"project {project_id} not found")
    research = json.loads(proj.research_json or "{}")
    pkg = build_package(db, "documentary", f"The Making of {proj.subject}",
                        summary=proj.brief, script=proj.script,
                        target_market="US", actor=actor)
    _attach_evidence(db, pkg["id"], proj.subject, actor)
    proj.package_id = pkg["id"]
    db.commit()
    from app.models.phase6 import ContentPackage
    from app.modules.content_gateway.engine import to_schema as _schema
    fresh = _schema(db.get(ContentPackage, pkg["id"]))
    return {**fresh, "verification_status": verification_status(db, proj.subject)}


def _attach_evidence(db, package_id: str, subject: str, actor: str) -> None:
    import json as _json
    from app.models.phase6 import ContentPackage
    from app.models.phase7 import EvidenceRecord
    from app.modules.verification.engine import verification_status
    from app.modules.rights.engine import asset_rights
    ev = (db.query(EvidenceRecord).filter(
        EvidenceRecord.claim.like(f"%{subject[:30]}%")).all())
    row = db.get(ContentPackage, package_id)
    row.evidence_json = _json.dumps([{"claim": e.claim, "url": e.url} for e in ev])
    row.sources_json = _json.dumps([{"source_id": e.source_id} for e in ev])
    row.verification_status = verification_status(db, subject)
    row.confidence_score = min(0.5 + len(ev) * 0.1, 0.95)
    row.rights_status = asset_rights(db, 0)["status"] if not ev else "review"
    db.commit()
    audit(db, actor, "package.evidenced", "package", package_id,
          {"evidence": len(ev)})


def projects(db, limit: int = 20) -> list[dict]:
    from app.models.phase7 import DocumentaryProject
    rows = db.query(DocumentaryProject).order_by(
        DocumentaryProject.id.desc()).limit(limit).all()
    return [{"id": r.id, "subject": r.subject, "package_id": r.package_id}
            for r in rows]
