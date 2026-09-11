"""Breakout Detection Engine: viral songs, breakout artists, movements, shifts."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("song", "artist", "movement", "genre_shift")
VIRAL_THRESHOLD = 2.0  # velocity above this = potential viral


def scan(db, actor: str = "breakout") -> list[dict]:
    """Detect breakout signals from discovery velocity + trend migration."""
    from app.models.phase4 import BreakoutAlert
    from app.modules.discovery.engine import discovery_report
    from app.modules.market_intelligence.engine import trend_migration
    alerts = []
    for r in discovery_report(db, limit=20):
        if float(r["velocity"] or 0) >= VIRAL_THRESHOLD:
            alerts.append(("artist", r["artist"], float(r["velocity"])))
    for m in trend_migration(db)[:10]:
        if m["countries"] >= 3:
            alerts.append(("song", f"{m['title']} — {m['artist']}",
                           float(m["score"]) / 100))
    out = []
    for kind, subject, signal in alerts[:15]:
        row = BreakoutAlert(kind=kind, subject=subject, signal=round(signal, 2))
        db.add(row)
        out.append({"kind": kind, "subject": subject, "signal": round(signal, 2)})
    db.commit()
    audit(db, actor, "breakout.scanned", "breakout", "", {"alerts": len(out)})
    return out


def watchlist(db, acknowledged: bool = False, limit: int = 20) -> list[dict]:
    from app.models.phase4 import BreakoutAlert
    rows = (db.query(BreakoutAlert)
            .filter(BreakoutAlert.acknowledged.is_(acknowledged))
            .order_by(BreakoutAlert.signal.desc()).limit(limit).all())
    return [{"id": r.id, "kind": r.kind, "subject": r.subject, "signal": r.signal}
            for r in rows]


def acknowledge(db, alert_id: int, actor: str = "executive"):
    from app.models.phase4 import BreakoutAlert
    row = db.get(BreakoutAlert, alert_id)
    if row is None:
        raise ValueError(f"alert {alert_id} not found")
    row.acknowledged = True
    db.commit()
    audit(db, actor, "breakout.acknowledged", "breakout", row.id, {})
    return row


def executive_recommendations(db, limit: int = 5) -> list[dict]:
    items = watchlist(db, limit=limit)
    return [{"subject": i["subject"],
             "recommendation": f"fast-track {i['kind']} coverage of "
                               f"'{i['subject']}' (signal {i['signal']}) — "
                               "publish within 24h",
             "priority": limit - n} for n, i in enumerate(items)]
