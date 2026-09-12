"""Real asset acquisition: official photos/videos, press kits, documentary
footage, public-domain archives, news and historical imagery.

Every asset carries: source, license, trust_score, rights_status, acquired_at.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

# Hierarchy rank (lower = preferred). AI is always last.
KIND_RANK = {
    "real_footage": 0,
    "real_photo": 1,
    "licensed": 2,
    "public_domain": 3,
    "ai_generated": 4,
}

CATEGORIES = ("official_photo", "official_video", "press", "documentary",
              "archive", "news", "historical", "licensed_stock", "generated")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest(source: str, license: str, trust_score: float,
             rights_status: str, **extra) -> dict:
    """Build the mandatory asset manifest envelope."""
    return {
        "source": source,
        "license": license,
        "trust_score": max(0.0, min(1.0, float(trust_score))),
        "rights_status": (rights_status or "UNKNOWN").upper(),
        "acquired_at": _now_iso(),
        **extra,
    }


def normalize_source(entry: dict, default_trust: float = 0.5) -> dict:
    """Pulse-provided source → asset candidate with scored trust."""
    source = str(entry.get("source") or entry.get("url") or entry.get("name", "pulse-provided"))
    license = str(entry.get("license") or entry.get("rights") or "")
    rights = str(entry.get("rights_status") or entry.get("rights") or "UNKNOWN")
    trust = float(entry.get("trust_score", default_trust))
    # Verified evidence boosts trust; unknown provenance lowers it.
    if entry.get("verified") is True:
        trust = min(1.0, trust + 0.2)
    if entry.get("type") in ("rumor", "unverified"):
        trust = max(0.0, trust - 0.3)
    kind = str(entry.get("kind", "real_photo"))
    if kind not in KIND_RANK:
        kind = "real_photo"
    return manifest(source, license, trust, rights,
                    kind=kind,
                    category=str(entry.get("category", "news")),
                    duration_seconds=float(entry.get("duration_seconds", 0.0)),
                    tags=list(entry.get("tags", [])))


def normalize_evidence(entry: dict) -> dict:
    """Pulse-provided evidence → asset candidate (evidence outranks bare sources)."""
    base = normalize_source(entry, default_trust=0.6)
    base["trust_score"] = min(1.0, base["trust_score"] + 0.1)
    base["evidence_backed"] = True
    return base


def rank_key(asset: dict) -> tuple:
    """Sort key: hierarchy rank first, then trust desc, then source name."""
    return (KIND_RANK.get(asset.get("kind", "ai_generated"), 4),
            -float(asset.get("trust_score", 0.0)),
            str(asset.get("source", "")))


def order(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=rank_key)


SEED_CATALOG: list[dict] = [
    {"asset_id": "seed-doc-001", "kind": "real_footage", "category": "documentary",
     "source": "factory-seed: documentary footage library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 30.0,
     "tags": ["documentary", "general"]},
    {"asset_id": "seed-press-001", "kind": "real_photo", "category": "press",
     "source": "factory-seed: press photo library", "license": "editorial-use attribution-required",
     "trust_score": 0.75, "rights_status": "RESTRICTED", "duration_seconds": 5.0,
     "tags": ["press", "general"]},
    {"asset_id": "seed-archive-001", "kind": "public_domain", "category": "archive",
     "source": "factory-seed: public-domain archive", "license": "public-domain",
     "trust_score": 0.7, "rights_status": "CLEARED", "duration_seconds": 20.0,
     "tags": ["archive", "historical", "history"]},
    {"asset_id": "seed-official-001", "kind": "real_photo", "category": "official_photo",
     "source": "factory-seed: official photo library", "license": "official-use attribution-required",
     "trust_score": 0.85, "rights_status": "RESTRICTED", "duration_seconds": 5.0,
     "tags": ["official", "portrait"]},
]


def seed_catalog(db) -> int:
    """Insert seed catalog rows if empty. Returns rows inserted."""
    from app.models.production import ProductionAsset
    if db.query(ProductionAsset).count():
        return 0
    now = time.time()
    for seed in SEED_CATALOG:
        db.add(ProductionAsset(asset_id=seed["asset_id"], kind=seed["kind"],
                               category=seed["category"], source=seed["source"],
                               license=seed["license"], trust_score=seed["trust_score"],
                               rights_status=seed["rights_status"],
                               duration_seconds=seed["duration_seconds"],
                               meta_json={"tags": seed["tags"], "seed": True},
                               acquired_at=now))
    try:
        db.commit()
    except Exception:
        # Concurrent seeder won the race (UNIQUE on asset_id): keep existing rows.
        db.rollback()
        return 0
    return len(SEED_CATALOG)


def catalog_availability(db) -> dict:
    """Counts by kind for the capacity report."""
    from app.models.production import ProductionAsset
    rows = db.query(ProductionAsset).all()
    by_kind: dict[str, int] = {}
    for row in rows:
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
    return {"total": len(rows), "by_kind": by_kind}
