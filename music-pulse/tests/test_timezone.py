import pytest
from app.modules.timezone.engine import (
    ZONES, COUNTRY_ZONES, heatmap, best_posting_times,
    schedule_for_country, minutes_until_best, auto_reschedule,
)
from app.modules.content.engine import generate_content, persist_content
from app.modules.publisher.engine import queue_post


def test_zones_cover_requirements():
    assert set(ZONES) == {"ET", "CT", "MT", "PT", "UK", "AU", "DE"}
    assert set(COUNTRY_ZONES) == {"US", "CA", "UK", "AU", "DE"}
    assert COUNTRY_ZONES["US"] == ["ET", "CT", "MT", "PT"]


def test_heatmap_defaults_and_best(db):
    hm = heatmap(db, "US")
    assert len(hm) == 24 and max(hm, key=hm.get) in range(17, 23)
    best = best_posting_times("DE", n=3, db=db)
    assert len(best) == 3 and all("next_utc" in b for b in best)
    with pytest.raises(ValueError):
        heatmap(db, "XX")


def test_heatmap_uses_real_data(db):
    from app.modules.analytics.engine import record_metric
    record_metric(db, views=1000, engagement=900, topic="peak-test")
    hm = heatmap(db, "US")
    assert sum(hm.values()) > 0


def test_schedule_and_autoreschedule(db):
    dt = schedule_for_country("UK", db=db)
    assert (dt.hour, dt.minute) is not None
    assert minutes_until_best("US", db=db) >= 0
    c = persist_content(db, generate_content("short", "TZ Song"))
    job = queue_post(db, c.id, "log", delay_minutes=0)
    job2 = auto_reschedule(db, job.id, "AU", actor="test")
    assert job2.scheduled_at is not None
    with pytest.raises(ValueError):
        auto_reschedule(db, 99999)


def test_publisher_auto_selects_best_time(db):
    c = persist_content(db, generate_content("news", "Auto Song"))
    job = queue_post(db, c.id, "log", delay_minutes=None, country="US")
    assert job.scheduled_at is not None and job.status == "queued"
