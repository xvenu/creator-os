"""Rights & license validation. Only production decisions, never business ones.

Statuses: CLEARED | RESTRICTED | UNKNOWN | BLOCKED.
BLOCKED assets are never usable, in any production mode.
UNKNOWN assets are flagged and excluded from REALITY_ONLY.
"""
from __future__ import annotations

STATUSES = ("CLEARED", "RESTRICTED", "UNKNOWN", "BLOCKED")

_BLOCKED_MARKERS = ("prohibited", "do-not-use", "no-use", "blocked", "embargoed")
_ATTRIBUTION_MARKERS = ("attribution", "credit", "by-")
_NON_COMMERCIAL_MARKERS = ("non-commercial", "noncommercial", "nc-")
_EDITORIAL_MARKERS = ("editorial", "editorial-only")
_GEO_MARKERS = ("geo-", "region-", "territory-")


def validate(rights_status: str = "", license: str = "") -> dict:
    """Classify one asset's usage rights. Pure function, no I/O."""
    status = (rights_status or "").strip().upper() or "UNKNOWN"
    lic = (license or "").strip().lower()

    if status == "BLOCKED" or any(m in lic for m in _BLOCKED_MARKERS):
        return {"status": "BLOCKED", "usable": False,
                "restrictions": ["prohibited-use"],
                "reason": "rights holder prohibits use"}

    if status == "CLEARED":
        restrictions = _restrictions_from_license(lic)
        return {"status": "CLEARED", "usable": True,
                "restrictions": restrictions,
                "reason": "cleared for production use"}

    if status == "RESTRICTED":
        restrictions = _restrictions_from_license(lic) or ["restricted-use"]
        return {"status": "RESTRICTED", "usable": True,
                "restrictions": restrictions,
                "reason": "usable within stated restrictions"}

    return {"status": "UNKNOWN", "usable": True, "needs_review": True,
            "restrictions": ["unverified-rights"],
            "reason": "rights unknown — flagged for review"}


def _restrictions_from_license(lic: str) -> list[str]:
    out: list[str] = []
    if any(m in lic for m in _ATTRIBUTION_MARKERS):
        out.append("attribution-required")
    if any(m in lic for m in _NON_COMMERCIAL_MARKERS):
        out.append("non-commercial")
    if any(m in lic for m in _EDITORIAL_MARKERS):
        out.append("editorial-only")
    out.extend(m for m in _GEO_MARKERS if m in lic)
    return out


def is_usable(validation: dict, production_mode: str = "REALITY_FIRST") -> bool:
    """Mode-aware usability gate. BLOCKED is never usable."""
    if validation["status"] == "BLOCKED":
        return False
    if validation["status"] == "UNKNOWN" and production_mode == "REALITY_ONLY":
        return False
    return bool(validation.get("usable", False))


def validate_batch(assets: list[dict], production_mode: str = "REALITY_FIRST") -> dict:
    """Validate many assets; blocked items are separated, never silently dropped."""
    cleared, blocked = [], []
    for asset in assets:
        result = validate(asset.get("rights_status", ""), asset.get("license", ""))
        entry = {**asset, "rights_check": result,
                 "usable": is_usable(result, production_mode)}
        (cleared if entry["usable"] else blocked).append(entry)
    return {"usable": cleared, "blocked": blocked,
            "summary": {"usable": len(cleared), "blocked": len(blocked),
                        "total": len(assets)}}
