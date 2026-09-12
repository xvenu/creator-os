"""Queue worker: picks up `created` requests oldest-first and executes them."""
from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.database import get_session_factory, init_db
from app.core.logging import configure_logging, get_logger
from app.services import creator_os as cos
from app.services import pipeline as pipeline_mod

log = get_logger("zoza-worker")


def run_once() -> int:
    from app.models.production import ProductionRequest
    settings = get_settings()
    db = get_session_factory()()
    try:
        row = (db.query(ProductionRequest)
               .filter_by(state="created").order_by(ProductionRequest.id).first())
        if row is None:
            return 0
        log.info("executing request %s", row.request_id)
        pipeline_mod.execute(db, row.request_id, settings.output_dir)
        return 1
    finally:
        db.close()


def main(poll_seconds: float = 2.0) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    log.info("zoza-factory worker started")
    while True:
        try:
            done = run_once()
            cos.heartbeat()
            time.sleep(0.5 if done else poll_seconds)
        except KeyboardInterrupt:
            break
        except Exception as exc:  # worker never dies on a bad request
            log.error("worker error: %s", exc)
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
