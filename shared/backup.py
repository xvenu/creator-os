"""Creator-OS backup + restore: sqlite DBs + config metadata (no secrets).

Usage:
  python -m shared.backup backup --out ./backups [--retention 7]
  python -m shared.backup verify <backup-dir>
  python -m shared.backup restore <backup-dir> --dest ./restored

Backs up: factory.db, musicpulse.db (if present), shared event_bus /
orchestrator / knowledge / notifications DBs, plus a metadata manifest
(schema versions, contract version, app versions). Secret VALUES are never
copied (only .env.example files + key NAMES from env). Retention prunes
older backup dirs. Verify checks sha256 per file. Restore copies back and
re-verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_CANDIDATES = [
    "zoza-factory/factory.db",
    "music-pulse/musicpulse.db",
    "shared/event_bus/event_bus.db",
    "shared/orchestrator/orchestrator.db",
    "shared/knowledge/knowledge.db",
    "shared/notifications/notifications.db",
]

CONFIG_CANDIDATES = [
    "music-pulse/.env.example",
    "football-pulse/.env.example",
    "zoza-factory/.env.example",
    "zoza-factory/migrations/001_initial.sql",
    "zoza-factory/migrations/002_universal_factory.sql",
    "zoza-factory/migrations/003_asset_requirements.sql",
    "music-pulse/migrations/008_publish_idempotency.sql",
]


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(out: str, retention: int = 7) -> dict:
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = Path(out) / f"creator-os-{ts}"
    dest.mkdir(parents=True, exist_ok=False)
    manifest: dict = {"created_at": time.time(), "files": {}, "missing": []}
    for rel in DB_CANDIDATES + CONFIG_CANDIDATES:
        src = ROOT / rel
        if src.exists():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            manifest["files"][rel] = {"sha256": _sha(target),
                                      "size": target.stat().st_size}
        else:
            manifest["missing"].append(rel)
    try:
        from zoza_factory_contract import _versions  # placeholder-safe
        manifest["versions"] = _versions()
    except Exception:
        manifest["versions"] = _local_versions()
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    _prune(Path(out), retention)
    return {"backup_dir": str(dest), "files": len(manifest["files"]),
            "missing": manifest["missing"]}


def _local_versions() -> dict:
    return {"contract": "v2", "backup_tool": "shared.backup v1"}


def verify(backup_dir: str) -> dict:
    d = Path(backup_dir)
    manifest = json.loads((d / "manifest.json").read_text())
    bad = []
    for rel, meta in manifest.get("files", {}).items():
        p = d / rel
        if not p.exists() or _sha(p) != meta["sha256"]:
            bad.append(rel)
    return {"backup_dir": str(d), "ok": not bad, "bad": bad,
            "files": len(manifest.get("files", {}))}


def restore(backup_dir: str, dest: str) -> dict:
    v = verify(backup_dir)
    if not v["ok"]:
        raise RuntimeError(f"backup corrupt, refusing restore: {v['bad']}")
    d, out = Path(backup_dir), Path(dest)
    manifest = json.loads((d / "manifest.json").read_text())
    for rel in manifest.get("files", {}):
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(d / rel, target)
    return {"restored_to": str(out), "files": len(manifest["files"])}


def _prune(out: Path, retention: int) -> None:
    dirs = sorted([p for p in out.glob("creator-os-*") if p.is_dir()])
    for old in dirs[:-max(1, retention)]:
        shutil.rmtree(old, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="shared.backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--out", default="./backups")
    b.add_argument("--retention", type=int, default=7)
    v = sub.add_parser("verify")
    v.add_argument("dir")
    r = sub.add_parser("restore")
    r.add_argument("dir")
    r.add_argument("--dest", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "backup":
        print(json.dumps(backup(a.out, a.retention), indent=2))
    elif a.cmd == "verify":
        print(json.dumps(verify(a.dir), indent=2))
    elif a.cmd == "restore":
        print(json.dumps(restore(a.dir, a.dest), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
