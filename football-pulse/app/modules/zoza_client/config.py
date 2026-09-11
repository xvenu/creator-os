"""Factory addressing + client tuning. Relocatable: no hard-coded home paths
in logic — resolution order is env → pulse-relative → home fallback."""
from __future__ import annotations

import os
from pathlib import Path

MAX_ATTEMPTS = 5
POLL_TIMEOUT_SECONDS = 5


def pulse_root() -> Path:
    return Path(__file__).resolve().parents[3]


def zoza_dir() -> str:
    explicit = os.environ.get("ZOZA_DIR", "").strip()
    if explicit:
        # Explicit configuration wins: a missing dir is unreachable,
        # never silently rerouted elsewhere.
        return str(Path(explicit).resolve()) if Path(explicit).is_dir() else ""
    sibling = pulse_root().parent / "Zoza_anime"
    # Repo layout keeps Zoza_anime next to creator-os/, i.e. two levels up.
    for candidate in (sibling, pulse_root().parents[1] / "Zoza_anime",
                      Path.home() / "Zoza_anime"):
        if candidate.is_dir():
            return str(candidate.resolve())
    return ""


def factory_jobs_dir() -> str:
    zdir = zoza_dir()
    return str(Path(zdir) / "jobs") if zdir else ""
