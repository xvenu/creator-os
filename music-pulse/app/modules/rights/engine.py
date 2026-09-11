"""Rights & Attribution Engine: every asset carries rights metadata."""
from __future__ import annotations

from app.core.audit import audit


def set_rights(db, asset_id: int, restriction: str = "", license: str = "unknown",
               owner: str = "", attribution_required: bool = True,
               actor: str = "rights"):
    from app.models.phase7 import RightsRecord, MediaAsset
    if db.get(MediaAsset, asset_id) is None and asset_id != 0:
        raise ValueError(f"asset {asset_id} not found")
    row = RightsRecord(asset_id=asset_id, restriction=restriction, license=license,
                       owner=owner, attribution_required=attribution_required)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "rights.set", "rights", row.id, {"asset": asset_id})
    return row


def asset_rights(db, asset_id: int) -> dict:
    from app.models.phase7 import RightsRecord, MediaAsset
    asset = db.get(MediaAsset, asset_id)
    rec = (db.query(RightsRecord).filter(RightsRecord.asset_id == asset_id)
           .order_by(RightsRecord.id.desc()).first())
    if rec is None:
        return {"asset_id": asset_id, "status": "unknown",
                "attribution": asset.attribution if asset else ""}
    blocked = rec.license.lower() in ("all-rights-reserved", "do-not-use")
    return {"asset_id": asset_id,
            "status": "blocked" if blocked else "cleared",
            "license": rec.license, "owner": rec.owner,
            "attribution": asset.attribution if asset else "",
            "attribution_required": rec.attribution_required}
