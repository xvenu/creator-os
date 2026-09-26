"""Backup/restore proof: backup → destroy → restore → verify ownership/data."""
from __future__ import annotations

import json
import os
import sqlite3
import sys


def test_backup_verify_restore_cycle(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    from shared import backup as bkp
    # Stage a throwaway DB mimicking a pulse store with owned jobs.
    src = tmp_path / "stage"
    (src / "shared" / "event_bus").mkdir(parents=True)
    dbp = src / "shared" / "event_bus" / "event_bus.db"
    c = sqlite3.connect(str(dbp))
    c.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, source_pulse TEXT, body TEXT)")
    c.execute("INSERT INTO events (source_pulse, body) VALUES ('music-pulse','hello')")
    c.commit()
    c.close()
    out = tmp_path / "backups"
    # Exercise the real tool against the staged root via monkeypatched ROOT.
    old_root = bkp.ROOT
    bkp.ROOT = src
    try:
        res = bkp.backup(str(out), retention=2)
        assert res["files"] >= 1
        v = bkp.verify(res["backup_dir"])
        assert v["ok"] is True
        # Destroy then restore.
        dbp.unlink()
        assert not dbp.exists()
        r = bkp.restore(res["backup_dir"], str(tmp_path / "restored"))
        assert r["files"] >= 1
        rp = tmp_path / "restored" / "shared" / "event_bus" / "event_bus.db"
        c = sqlite3.connect(str(rp))
        row = c.execute("SELECT source_pulse, body FROM events").fetchone()
        c.close()
        assert row == ("music-pulse", "hello")  # ownership + data survive
    finally:
        bkp.ROOT = old_root


def test_backup_never_copies_secrets(tmp_path):
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    from shared import backup as bkp
    assert not any(".env" == p.rsplit("/", 1)[-1] and "example" not in p
                   for p in bkp.DB_CANDIDATES + bkp.CONFIG_CANDIDATES)
