"""Zoza refactor tests: package builder → factory job JSON."""
from __future__ import annotations

import pytest

from app.modules.zoza_client.package import (
    REQUIRED_PACKAGE_FIELDS,
    build_zoza_package,
    to_zoza_job,
)


def test_package_has_required_fields(sample_content_package):
    package = build_zoza_package(sample_content_package)
    for field in REQUIRED_PACKAGE_FIELDS:
        assert field in package, f"missing {field}"
    assert package["package_id"] == "11111111-1111-1111-1111-111111111111"
    assert "record signing" in package["script"]
    assert package["target_platform"] == "youtube,tiktok"
    assert package["priority"] == 80  # opportunity_score 0.8 × 100


def test_package_explicit_priority_wins(sample_content_package):
    sample_content_package["priority"] = 95
    assert build_zoza_package(sample_content_package)["priority"] == 95


def test_package_rejects_missing_title(sample_content_package):
    del sample_content_package["title"]
    with pytest.raises(ValueError):
        build_zoza_package(sample_content_package)


def test_package_rejects_empty_script(sample_content_package):
    sample_content_package["script"] = {"hook": "", "body": "", "outro": ""}
    with pytest.raises(ValueError):
        build_zoza_package(sample_content_package)


def test_package_accepts_plain_string_script(sample_content_package):
    sample_content_package["script"] = "Plain narration text here."
    package = build_zoza_package(sample_content_package)
    assert package["script"] == "Plain narration text here."


def test_job_document_shape(sample_content_package):
    package = build_zoza_package(sample_content_package)
    job = to_zoza_job(package)
    assert job["job_id"].startswith("fp-")
    assert job["state"] == "QUEUED"
    assert job["publish_targets"] == []  # factory never publishes
    assert job["music"]["source"] == "none"
    assert job["voiceover_script"] == package["script"]
    assert len(job["scenes"]) >= 1
    assert all(s["status"] == "PENDING" for s in job["scenes"])


def test_job_rejects_incomplete_package():
    with pytest.raises(ValueError):
        to_zoza_job({"package_id": "x"})


def test_job_scenes_bounded():
    package = {"package_id": "p", "title": "t", "summary": "s",
               "script": " ".join(f"Sentence {i}." for i in range(50)),
               "visual_requirements": [], "voice_requirements": {},
               "target_platform": "youtube", "priority": 1}
    assert len(to_zoza_job(package)["scenes"]) <= 8
