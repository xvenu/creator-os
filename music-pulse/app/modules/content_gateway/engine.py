"""Content Export Gateway: MusicPulse intelligence → Zoza-ready packages."""
from __future__ import annotations
import json
import uuid
from datetime import datetime

from app.core.audit import audit

PACKAGE_TYPES = ("news", "profile", "review", "ranking", "trend_report",
                 "breakout_report", "explainer", "documentary")


def build_package(db, type: str, title: str, summary: str = "", script: str = "",
                  hashtags: list | None = None, keywords: list | None = None,
                  thumbnail_brief: str = "", video_brief: str = "",
                  target_market: str = "US", target_platform: str = "youtube",
                  priority_score: float = 0.0, predicted_views: float = 0.0,
                  predicted_revenue: float = 0.0, actor: str = "gateway") -> dict:
    from app.models.phase6 import ContentPackage
    if type not in PACKAGE_TYPES:
        raise ValueError(f"unknown package type: {type}")
    pkg_id = uuid.uuid4().hex[:12]
    row = ContentPackage(
        id=pkg_id, type=type, title=title, summary=summary, script=script,
        hashtags_json=json.dumps(hashtags or []), keywords_json=json.dumps(keywords or []),
        thumbnail_brief=thumbnail_brief, video_brief=video_brief,
        target_market=target_market.upper(), target_platform=target_platform,
        priority_score=priority_score, predicted_views=predicted_views,
        predicted_revenue=predicted_revenue)
    db.add(row)
    db.commit()
    audit(db, actor, "package.created", "package", pkg_id, {"type": type})
    try:
        from app.core.shared import event_bus
        event_bus.publish("PACKAGE_CREATED", {"package_id": pkg_id, "type": type},
                          source_pulse="music-pulse")
    except Exception:
        pass
    return to_schema(row)


def to_schema(row) -> dict:
    return {"id": row.id, "type": row.type, "title": row.title,
            "summary": row.summary, "script": row.script,
            "hashtags": json.loads(row.hashtags_json or "[]"),
            "keywords": json.loads(row.keywords_json or "[]"),
            "thumbnail_brief": row.thumbnail_brief, "video_brief": row.video_brief,
            "target_market": row.target_market, "target_platform": row.target_platform,
            "priority_score": row.priority_score, "predicted_views": row.predicted_views,
            "predicted_revenue": row.predicted_revenue,
            "generated_at": str(row.generated_at),
            # Phase 7 evidence extension — Zoza receives sources + rights metadata
            "evidence": json.loads(getattr(row, "evidence_json", "[]") or "[]"),
            "sources": json.loads(getattr(row, "sources_json", "[]") or "[]"),
            "verification_status": getattr(row, "verification_status", "unverified"),
            "confidence_score": getattr(row, "confidence_score", 0.0),
            "rights_status": getattr(row, "rights_status", "unknown"),
            "attribution": json.loads(getattr(row, "attribution_json", "[]") or "[]")}


def from_opportunity(db, topic: str, kind: str = "news", market: str = "US",
                     platform: str = "youtube", actor: str = "gateway") -> dict:
    """Build a package from live intelligence (trends + prediction + formats)."""
    from app.modules.video_opportunities.engine import score_topic
    from app.modules.formats.engine import recommend_format
    scored = score_topic(db, topic, market)
    fmt = recommend_format(db, topic)
    briefs = {
        "news": (f"{topic} explodes across the charts — the full story",
                 f"Cover the rise of {topic}: chart positions, fan reaction, what's next."),
        "profile": (f"Who is behind {topic}?", f"Deep-dive biography and sound breakdown."),
        "review": (f"Is {topic} worth the hype?", "Honest review with score and verdict."),
        "ranking": (f"Where {topic} ranks right now", "Countdown format with chart data."),
        "trend_report": (f"The {topic} trend wave", "Data-driven trend report."),
        "breakout_report": (f"{topic}: breakout alert", "Early-signal breakout coverage."),
        "explainer": (f"{topic} explained", "Explain the sound, roots and influence."),
        "documentary": (f"The making of {topic}", "Mini-documentary concept."),
    }
    title, vbrief = briefs.get(kind, briefs["news"])
    return build_package(
        db, kind, title, summary=f"{topic} is moving in {market}.",
        script=f"Hook: {topic} is blowing up. Body: charts, story, fan angle. CTA: follow.",
        hashtags=["#MusicPulse", "#NowPlaying", f"#{market}Music"],
        keywords=[topic, market, kind], thumbnail_brief=f"{topic} + bold chart graphic",
        video_brief=f"{vbrief} Format: {fmt['format']}.",
        target_market=market, target_platform=platform,
        priority_score=scored["score"], predicted_views=scored["predicted_views"],
        predicted_revenue=scored["predicted_revenue"], actor=actor)


def export_json(db, package_id: str, actor: str = "gateway") -> dict:
    from app.models.phase6 import ContentPackage, PackageExport
    row = db.get(ContentPackage, package_id)
    if row is None:
        raise ValueError(f"package {package_id} not found")
    db.add(PackageExport(package_id=package_id, channel="json", status="sent"))
    db.commit()
    audit(db, actor, "package.exported", "package", package_id, {"channel": "json"})
    return to_schema(row)


def queue_export(db, package_id: str, actor: str = "gateway") -> dict:
    """Queue export: enqueue package for the Zoza dispatcher worker."""
    from app.models.phase6 import PackageExport
    from app.core.redis_queue import enqueue_job
    if db.get(__import__("app.models.phase6", fromlist=["ContentPackage"]).ContentPackage,
              package_id) is None:
        raise ValueError(f"package {package_id} not found")
    try:
        enqueue_job("zoza", "app.modules.zoza.engine.dispatch_package",
                    package_id)
        status = "queued"
    except Exception:
        status = "queued-local"  # redis unavailable (tests/dev): dispatcher polls DB
    db.add(PackageExport(package_id=package_id, channel="queue", status=status))
    db.commit()
    audit(db, actor, "package.exported", "package", package_id, {"channel": "queue"})
    return {"package_id": package_id, "status": status}


def list_packages(db, limit: int = 50) -> list[dict]:
    from app.models.phase6 import ContentPackage
    rows = db.query(ContentPackage).order_by(
        ContentPackage.priority_score.desc()).limit(limit).all()
    return [{"id": r.id, "type": r.type, "title": r.title,
             "priority": r.priority_score, "market": r.target_market} for r in rows]
