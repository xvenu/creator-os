"""Real asset acquisition: official photos/videos, press kits, documentary
footage, public-domain archives, news and historical imagery.

Every asset carries: source, license, trust_score, rights_status, acquired_at.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

# Hierarchy rank (lower = preferred). AI is always last.
# New families slot into the existing ladder without changing the order
# of the original five kinds (AI stays last by construction).
KIND_RANK = {
    "real_footage": 0,
    "film_scene": 0,
    "real_photo": 1,
    "anime_keyframe": 1,
    "anime_background": 1,
    "product_shot": 1,
    "licensed": 2,
    "brand_asset": 2,
    "public_domain": 3,
    "licensed_stock": 3,
    "ai_generated": 4,
    "ai_video": 4,
    "ai_image": 4,
}

# AI kinds (synthetic, factory-generated) — always ranked last.
AI_KINDS = ("ai_generated", "ai_video", "ai_image")

CATEGORIES = ("official_photo", "official_video", "press", "documentary",
              "archive", "news", "historical", "licensed_stock", "generated",
              "anime", "film", "commercial", "product", "brand")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest(source: str, license: str, trust_score: float,
             rights_status: str, **extra) -> dict:
    """Build the mandatory asset manifest envelope."""
    attribution = str(extra.get("attribution", "") or "")
    if not attribution and "attribution" in (license or "").lower():
        attribution = "attribution-required"
    out = {
        "source": source,
        "license": license,
        "trust_score": max(0.0, min(1.0, float(trust_score))),
        "rights_status": (rights_status or "UNKNOWN").upper(),
        "acquired_at": _now_iso(),
        "provenance": str(extra.get("provenance", source)),
        "attribution": attribution,
        "content_hash": str(extra.get("content_hash", _hash_source(source))),
    }
    out.update({k: v for k, v in extra.items()
                if k not in ("provenance", "attribution", "content_hash")})
    # Prefer file-backed hash when a real local file is attached.
    _p = str(out.get("path", "") or "")
    if _p:
        try:
            from pathlib import Path as _P
            fp = _P(_p)
            if fp.exists():
                out.update(_file_facts(fp))
                out["path"] = str(fp.resolve())
        except Exception:
            pass
    return out


def _hash_source(source: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


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
    out = manifest(source, license, trust, rights,
                   kind=kind,
                   category=str(entry.get("category", "news")),
                   duration_seconds=float(entry.get("duration_seconds", 0.0)),
                   tags=list(entry.get("tags", [])))
    # Real file backing: pulse-supplied local media is hashed + measured.
    for key in ("path", "file"):
        p = str(entry.get(key, "") or "")
        if p:
            from pathlib import Path as _P
            fp = _P(p)
            if fp.exists() and fp.is_file():
                out["path"] = str(fp.resolve())
                out.update(_file_facts(fp))
            break
    return out


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


def is_ai(asset: dict) -> bool:
    return str(asset.get("kind", "")) in AI_KINDS


def order(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=rank_key)


SEED_CATALOG: list[dict] = [
    {"asset_id": "seed-doc-001", "media": "doc", "kind": "real_footage", "category": "documentary",
     "source": "factory-seed: documentary footage library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 30.0,
     "tags": ["documentary", "general"]},
    {"asset_id": "seed-press-001", "media": "press", "kind": "real_photo", "category": "press",
     "source": "factory-seed: press photo library", "license": "editorial-use attribution-required",
     "trust_score": 0.75, "rights_status": "RESTRICTED", "duration_seconds": 5.0,
     "tags": ["press", "general"]},
    {"asset_id": "seed-archive-001", "media": "archive", "kind": "public_domain", "category": "archive",
     "source": "factory-seed: public-domain archive", "license": "public-domain",
     "trust_score": 0.7, "rights_status": "CLEARED", "duration_seconds": 20.0,
     "tags": ["archive", "historical", "history"]},
    {"asset_id": "seed-official-001", "media": "official", "kind": "real_photo", "category": "official_photo",
     "source": "factory-seed: official photo library", "license": "official-use attribution-required",
     "trust_score": 0.85, "rights_status": "RESTRICTED", "duration_seconds": 5.0,
     "tags": ["official", "portrait"]},
    {"asset_id": "seed-anime-001", "media": "anime-bg", "kind": "anime_background", "category": "anime",
     "source": "factory-seed: anime background library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 10.0,
     "tags": ["anime", "background", "general"]},
    {"asset_id": "seed-anime-002", "media": "anime-kf", "kind": "anime_keyframe", "category": "anime",
     "source": "factory-seed: anime keyframe library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 5.0,
     "tags": ["anime", "character", "general"]},
    {"asset_id": "seed-film-001", "media": "film", "kind": "film_scene", "category": "film",
     "source": "factory-seed: cinematic b-roll library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 30.0,
     "tags": ["film", "cinematic", "movie", "general"]},
    {"asset_id": "seed-ad-001", "media": "product", "kind": "product_shot", "category": "product",
     "source": "factory-seed: commercial product frame library", "license": "factory-licensed",
     "trust_score": 0.8, "rights_status": "CLEARED", "duration_seconds": 5.0,
     "tags": ["ad", "commercial", "product", "general"]},
]


def seed_catalog(db, media_dir: str = "") -> int:
    """Insert seed catalog rows if empty. Generates real PNG media files so
    seeded real_photo/anime assets are decodable images (hashed + measured)."""
    from app.models.production import ProductionAsset
    existing = db.query(ProductionAsset).all()
    if existing:
        # Backfill pre-existing rows (pre-media seeds) with real PNG paths once.
        try:
            if not any((r.meta_json or {}).get("path") for r in existing):
                media = _ensure_seed_media(media_dir)
                _by_id = {s["asset_id"]: s for s in SEED_CATALOG}
                for r in existing:
                    seed = _by_id.get(r.asset_id, {})
                    key = seed.get("media", "")
                    if key and key in media:
                        meta = dict(r.meta_json or {})
                        meta.update({"path": media[key],
                                     **_file_facts_str(media[key])})
                        r.meta_json = meta
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return 0
    import time
    media = _ensure_seed_media(media_dir)
    now = time.time()
    seeds = [dict(s) for s in SEED_CATALOG]
    for s in seeds:
        key = s.get("media")
        if key and key in media:
            s["meta_extra"] = {"path": media[key], **_file_facts_str(media[key])}
    for seed in seeds:
        meta = {"tags": seed["tags"], "seed": True}
        if seed.get("meta_extra"):
            meta.update(seed["meta_extra"])
        if "media" in seed:
            seed = {k: v for k, v in seed.items() if k != "media"}
        db.add(ProductionAsset(asset_id=seed["asset_id"], kind=seed["kind"],
                               category=seed["category"], source=seed["source"],
                               license=seed["license"], trust_score=seed["trust_score"],
                               rights_status=seed["rights_status"],
                               duration_seconds=seed["duration_seconds"],
                               meta_json=meta,
                               acquired_at=now))
    try:
        db.commit()
    except Exception:
        # Concurrent seeder won the race (UNIQUE on asset_id): keep existing rows.
        db.rollback()
        return 0
    return len(seeds)


def _file_facts(fp) -> dict:
    """Hash + size (+ dimensions for images) of a real local file."""
    import hashlib
    try:
        raw = fp.read_bytes()
        out = {"content_hash": "sha256:" + hashlib.sha256(raw).hexdigest()[:32],
               "file_size": len(raw)}
        try:
            from PIL import Image as _Img
            with _Img.open(fp) as im:
                out["width"], out["height"] = im.size
        except Exception:
            pass
        return out
    except Exception:
        return {}


def _file_facts_str(path: str) -> dict:
    from pathlib import Path as _P
    return _file_facts(_P(path))


def _ensure_seed_media(media_dir: str = "") -> dict[str, str]:
    """Create deterministic real PNGs (gradient + shapes) for seed assets."""
    from pathlib import Path as _P
    base = _P(media_dir) if media_dir else _P("catalog_media")
    base.mkdir(parents=True, exist_ok=True)
    specs = {
        "doc": ((1280, 720), (23, 32, 48), (90, 140, 200)),
        "press": ((640, 480), (70, 40, 40), (220, 180, 150)),
        "archive": ((640, 480), (50, 50, 45), (200, 200, 190)),
        "official": ((640, 480), (35, 55, 90), (150, 190, 240)),
        "anime-bg": ((1280, 720), (58, 41, 76), (140, 200, 255)),
        "anime-kf": ((960, 540), (76, 53, 29), (255, 210, 140)),
        "film": ((1280, 720), (29, 74, 74), (255, 230, 180)),
        "product": ((720, 720), (240, 240, 245), (60, 120, 200)),
    }
    out: dict[str, str] = {}
    for key, (size, c1, c2) in specs.items():
        p = base / f"seed-{key}.png"
        if not p.exists():
            _write_gradient_png(p, size[0], size[1], c1, c2)
        out[key] = str(p.resolve())
    return out


def _write_gradient_png(path, w: int, h: int, c1: tuple, c2: tuple) -> None:
    from PIL import Image as _Img, ImageDraw as _Draw
    img = _Img.new("RGB", (w, h), c1)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for x in range(0, w, 4):
            px[x, y] = tuple(int(a + (b - a) * (t * 0.7 + 0.3 * x / w)) for a, b in zip(c1, c2))
    d = _Draw.Draw(img)
    d.ellipse([w // 4, h // 4, 3 * w // 4, 3 * h // 4], outline=(255, 255, 255), width=6)
    d.rectangle([10, 10, w - 10, 40], outline=(255, 255, 255), width=2)
    img.save(str(path), "PNG")


def catalog_availability(db) -> dict:
    """Counts by kind for the capacity report."""
    from app.models.production import ProductionAsset
    rows = db.query(ProductionAsset).all()
    by_kind: dict[str, int] = {}
    for row in rows:
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
    return {"total": len(rows), "by_kind": by_kind}
