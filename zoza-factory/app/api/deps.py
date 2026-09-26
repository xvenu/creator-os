"""Request-scoped DB session + per-pulse bearer auth.

Auth model: `pulse_token_music` → music-pulse, `pulse_token_football` →
football-pulse, `factory_admin_token` → admin (all pulses). Tokens travel as
`Authorization: Bearer <token>` and never appear in exports, events, logs,
or API responses. When no tokens are configured (development), auth is
disabled and every request is treated as admin-local (explicitly marked).
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Header, HTTPException

from app.core.database import get_session_factory


def get_db() -> Iterator:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def auth_context(authorization: str = Header(default="", alias="Authorization")) -> dict:
    """Resolve the caller: {pulse | admin} or raise 401. Disabled when unconfigured."""
    from app.core.config import get_settings
    s = get_settings()
    table = {s.pulse_token_music: "music-pulse",
             s.pulse_token_football: "football-pulse"}
    table = {tok: pulse for tok, pulse in table.items() if tok}
    admin = s.factory_admin_token or ""
    if not table and not admin:
        return {"pulse": "", "admin": True, "auth_disabled": True}
    token = (authorization or "")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    else:
        token = token.strip()
    if admin and token == admin:
        return {"pulse": "", "admin": True, "auth_disabled": False}
    if token in table:
        return {"pulse": table[token], "admin": False, "auth_disabled": False}
    raise HTTPException(status_code=401, detail="invalid or missing factory credential")


def scope_check(ctx: dict, row_pulse: str) -> None:
    """Owner or admin may proceed; other pulses get 403 (no existence oracle beyond it)."""
    if ctx.get("admin"):
        return
    owner = ctx.get("pulse", "")
    if owner and owner == (row_pulse or ""):
        return
    # Unattributed legacy rows (pulse="") are readable by any authenticated pulse
    # to preserve pre-auth history; new rows always carry a pulse.
    if not row_pulse:
        return
    raise HTTPException(status_code=403, detail="not authorized for this pulse's request")
