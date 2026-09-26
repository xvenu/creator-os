"""Contract V2 freeze: canonical fields, version, compat layer, no duplicates."""
from __future__ import annotations

import os


def test_canonical_fields_and_version():
    from app.schemas import contract as c
    assert c.CONTRACT_VERSION == "v2"
    assert set(c.CANONICAL_FIELDS) == {
        "request_id", "pulse", "content_type", "goal", "style",
        "length_seconds", "urgency", "production_mode", "ai_generation_allowed",
        "sources", "evidence", "voice_profile", "target_audience", "priority",
    }
    assert set(c.CANONICAL_EXPORT_FIELDS) == {
        "job_id", "status", "video_path", "thumbnail_path", "metadata",
    }
    from app.schemas.contract import ProductionRequestIn
    for f in c.CANONICAL_FIELDS:
        assert f in ProductionRequestIn.model_fields, f"canonical field missing: {f}"


def test_compat_normalization_maps_example_shape():
    from app.schemas.contract import normalize_compat, ProductionRequestIn
    compat = {"request_id": "c1", "origin": "footballpulse",
              "content_type": "short_video", "language": "en",
              "script": "Hello world. Second line.",
              "assets": [{"source": "x", "license": "public-domain",
                          "trust_score": 0.9, "rights_status": "CLEARED"}],
              "style": "news",
              "output": {"format": "mp4", "resolution": "1080x1920"}}
    data = normalize_compat(compat)
    assert data["pulse"] == "footballpulse"
    assert data["content_type"] == "video"
    assert data["narration"].startswith("Hello world")
    assert data["sources"][0]["source"] == "x"
    req = ProductionRequestIn(**{**data, "goal": " Compat game ", "length_seconds": 30})
    assert req.pulse == "footballpulse" and req.content_type.value == "video"


def test_no_duplicate_contract_definitions():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/.."
    hits = []
    for base, _, files in os.walk(root):
        if ".venv" in base or "__pycache__" in base or ".git" in base:
            continue
        for fn in files:
            if fn.endswith(".py") and "test_" not in fn:
                p = os.path.join(base, fn)
                if p.endswith("zoza-factory/app/schemas/contract.py"):
                    continue
                with open(p) as fh:
                    blob = fh.read()
                if "class ProductionRequestIn" in blob or "class ProductionMode" in blob:
                    hits.append(p)
    assert hits == [], f"duplicate contract definitions: {hits}"
