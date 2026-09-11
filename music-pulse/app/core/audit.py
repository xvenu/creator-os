"""Full audit logging: DB-backed + stdlib logging."""
import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger

log = get_logger("audit")


def audit(db: Optional[Session], actor: str, action: str,
          entity_type: str = "", entity_id: str = "",
          details: Optional[dict[str, Any]] = None) -> None:
    """Write an audit record. Never raises — logs on failure."""
    payload = {
        "actor": actor, "action": action, "entity_type": entity_type,
        "entity_id": str(entity_id), "details": details or {},
        "ts": datetime.utcnow().isoformat(),
    }
    log.info("AUDIT %s", json.dumps(payload))
    if db is None:
        return
    try:
        from app.models.models import AuditLog
        db.add(AuditLog(
            actor=actor, action=action, entity_type=entity_type,
            entity_id=str(entity_id), details_json=json.dumps(details or {}),
        ))
        db.commit()
    except Exception as exc:  # pragma: no cover - audit must not break flows
        log.warning("audit db write failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
