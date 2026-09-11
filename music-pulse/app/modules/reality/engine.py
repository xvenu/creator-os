"""Reality Intelligence Layer: verified truth before generation."""
from __future__ import annotations
from datetime import datetime

from app.core.audit import audit


class SourceDiscoveryEngine:
    CURATED = [
        ("Artist Official Site", "artist", True),
        ("Label Press Room", "label", True),
        ("Billboard", "news", False),
        ("Rolling Stone", "news", False),
        ("Pitchfork", "news", False),
        ("Music Business Worldwide", "industry", False),
        ("Venue Announcements", "event", False),
        ("Festival Announcements", "event", False),
    ]

    @staticmethod
    def discover(db, actor: str = "reality") -> list[dict]:
        from app.models.phase7 import Source
        existing = {r.name for r in db.query(Source).all()}
        added = []
        for name, kind, official in SourceDiscoveryEngine.CURATED:
            if name not in existing:
                url = f"https://{name.lower().replace(' ', '')}.example.com"
                row = Source(name=name, url=url, kind=kind, official=official)
                db.add(row)
                added.append(name)
        db.commit()
        audit(db, actor, "reality.discovered", "source", "", {"added": len(added)})
        return {"added": added, "total": db.query(Source).count()}


class SourceTrustEngine:
    WEIGHTS = {"trust": 0.35, "freshness": 0.2, "authority": 0.25, "reliability": 0.2}

    @staticmethod
    def score(db, source_id: int, trust: float = 0.0, freshness: float = 0.0,
              authority: float = 0.0, reliability: float = 0.0,
              actor: str = "reality"):
        from app.models.phase7 import Source, SourceScore
        if db.get(Source, source_id) is None:
            raise ValueError(f"source {source_id} not found")
        row = SourceScore(source_id=source_id, trust=trust, freshness=freshness,
                          authority=authority, reliability=reliability)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, actor, "reality.scored", "source", source_id, {"trust": trust})
        return row

    @staticmethod
    def composite(db, source_id: int) -> float:
        from app.models.phase7 import SourceScore
        r = (db.query(SourceScore).filter(SourceScore.source_id == source_id)
             .order_by(SourceScore.id.desc()).first())
        if not r:
            return 0.0
        w = SourceTrustEngine.WEIGHTS
        return round(r.trust * w["trust"] + r.freshness * w["freshness"] +
                     r.authority * w["authority"] + r.reliability * w["reliability"], 3)


class EvidenceCollector:
    @staticmethod
    def collect(db, claim: str, source_id: int = 0, url: str = "",
                snippet: str = "", actor: str = "reality"):
        from app.models.phase7 import EvidenceRecord
        row = EvidenceRecord(claim=claim, source_id=source_id, url=url, snippet=snippet)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, actor, "reality.evidence", "evidence", row.id, {"claim": claim[:80]})
        return row


class FactValidationEngine:
    @staticmethod
    def validate(db, claim: str, actor: str = "reality") -> dict:
        """Cross-check claim against collected evidence + source trust."""
        from app.models.phase7 import EvidenceRecord
        from app.modules.verification.engine import verify_claim
        hits = db.query(EvidenceRecord).filter(
            EvidenceRecord.claim.like(f"%{claim[:40]}%")).all()
        return verify_claim(db, claim, "claim", actor,
                            evidence_count=len(hits))


class RealityEngine:
    @staticmethod
    def report(db, topic: str, actor: str = "reality") -> dict:
        """Reality Report: every major decision must reference one of these."""
        from app.modules.source_intelligence.engine import recommend_sources
        from app.modules.verification.engine import verify_claim
        verdict = verify_claim(db, topic, "story", actor)
        sources = recommend_sources(db, limit=5)
        return {"topic": topic, "generated_at": datetime.utcnow().isoformat(),
                "verification": verdict, "sources": sources,
                "reality_first": True}
