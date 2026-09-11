import pytest
from app.modules.reality.engine import (RealityEngine, SourceDiscoveryEngine, SourceTrustEngine,
                                        EvidenceCollector, FactValidationEngine)
from app.modules.source_intelligence.engine import register_source, source_history, recommend_sources
from app.modules.media_acquisition.engine import track_asset, asset_report
from app.modules.verification.engine import verify_claim, verification_status, verification_log
from app.modules.artist_intelligence.engine import upsert_profile, artist_report, top_artists
from app.modules.label_intelligence.engine import upsert_label, label_report, active_labels
from app.modules.newsroom.engine import write_report, reports
from app.modules.documentary.engine import build_project, to_package, projects
from app.modules.rights.engine import set_rights, asset_rights


def test_reality_layer(db):
    disc = SourceDiscoveryEngine.discover(db)
    assert disc["total"] == 8
    src = db.query(__import__("app.models.phase7", fromlist=["Source"]).Source).first()
    SourceTrustEngine.score(db, src.id, trust=0.9, freshness=0.8, authority=0.9,
                            reliability=0.85)
    assert SourceTrustEngine.composite(db, src.id) == pytest.approx(0.87, abs=0.01)
    with pytest.raises(ValueError):
        SourceTrustEngine.score(db, 99999, trust=1.0)
    ev = EvidenceCollector.collect(db, "Nova tops charts", source_id=src.id,
                                   url="http://press.test/1", snippet="Nova #1")
    assert ev.id > 0
    v = FactValidationEngine.validate(db, "Nova tops charts")
    assert v["verdict"] in ("verified", "unverified", "disputed", "insufficient")
    rep = RealityEngine.report(db, "Nova tops charts")
    assert rep["reality_first"] is True and "verification" in rep


def test_sources(db):
    s = register_source(db, "Label X Press", "press", official=True)
    assert recommend_sources(db)[0]["official"] is True
    assert source_history(db, s.id)["evidence_uses"] == 0
    assert recommend_sources(db, kind="press")[0]["name"] == "Label X Press"
    with pytest.raises(ValueError):
        register_source(db, "X", "galaxy")


def test_media_and_rights(db):
    a = track_asset(db, "Nova Press Photo", "photo", ref_url="http://label.test/nova.jpg",
                    rights_status="review", attribution="Label X")
    assert asset_report(db, kind="photo")[0]["title"] == "Nova Press Photo"
    set_rights(db, a.id, license="editorial-use", owner="Label X")
    r = asset_rights(db, a.id)
    assert r == {"asset_id": a.id, "status": "cleared", "license": "editorial-use",
                 "owner": "Label X", "attribution": "Label X",
                 "attribution_required": True}
    set_rights(db, a.id, license="do-not-use", owner="Label X")
    assert asset_rights(db, a.id)["status"] == "blocked"
    assert asset_rights(db, 424242)["status"] == "unknown"
    with pytest.raises(ValueError):
        track_asset(db, "X", "hologram")
    with pytest.raises(ValueError):
        set_rights(db, 99999)


def test_verification_matrix(db):
    assert verify_claim(db, "A", trusted_hits=2)["verdict"] == "verified"
    assert verify_claim(db, "B", evidence_count=0)["verdict"] == "insufficient"
    assert verify_claim(db, "C", evidence_count=1)["verdict"] == "unverified"
    assert verify_claim(db, "D", evidence_count=2, disputes=1)["verdict"] == "disputed"
    assert verification_status(db, "A") == "verified"
    assert verification_status(db, "never-seen") == "unverified"
    assert len(verification_log(db, verdict="verified")) == 1
    with pytest.raises(ValueError):
        verify_claim(db, "X", category="horoscope")


def test_artist_label_intel(db):
    upsert_profile(db, "Nova", label="Label X", genre="Pop", momentum=9.5)
    upsert_label(db, "Label X", kind="major", signings=3, activity=8.0)
    rep = artist_report(db, "Nova")
    assert rep["label"] == "Label X" and rep["momentum"] == 9.5
    assert top_artists(db)[0]["artist"] == "Nova"
    lab = label_report(db, "Label X")
    assert lab["roster"] == 1 and lab["kind"] == "major"
    assert active_labels(db)[0]["label"] == "Label X"
    with pytest.raises(ValueError):
        artist_report(db, "Nobody")
    with pytest.raises(ValueError):
        label_report(db, "Nobody")
    with pytest.raises(ValueError):
        upsert_label(db, "X", kind="planet")


def test_newsroom_documentary(db):
    r = write_report(db, "news", "Nova hits #1",
                     "Nova topped charts today.",
                     sources=[{"name": "Label X", "trusted": True},
                              {"name": "Charts", "trusted": True},
                              {"name": "Blog", "trusted": False}])
    assert r["verification"] == "verified"
    assert reports(db, kind="news")[0]["title"] == "Nova hits #1"
    with pytest.raises(ValueError):
        write_report(db, "gossip", "x", "y")
    upsert_profile(db, "Nova", momentum=9.0)
    EvidenceCollector.collect(db, "Nova hits #1")
    proj = build_project(db, "Nova")
    assert "research" in proj and proj["research"]["evidence"]
    pkg = to_package(db, proj["id"])
    assert pkg["type"] == "documentary" and pkg["evidence"]
    assert pkg["verification_status"] in ("verified", "unverified", "disputed", "insufficient")
    assert projects(db)[0]["package_id"] == pkg["id"]
    with pytest.raises(ValueError):
        to_package(db, 99999)


def test_reality_first_decision(db):
    from app.modules.executive.engine import ExecutiveAgent
    assert ExecutiveAgent.DECISION_PRIORITY[0] == "verified_reality"
    out = ExecutiveAgent.decide_reality_first(db, "unseen topic xyz")
    assert out["tier"] == "ai_inference" and "Abstain" in out["decision"]
    verify_claim(db, "Nova hits #1", trusted_hits=3)
    out2 = ExecutiveAgent.decide_reality_first(db, "Nova hits #1")
    assert out2["tier"] == "verified_reality"
