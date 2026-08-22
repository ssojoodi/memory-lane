import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .paths import database_path


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect(path=None):
    target = Path(path) if path else database_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    con = sqlite3.connect(target, timeout=3)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=3000")
    migrate(con)
    try:
        os.chmod(target, 0o600)
    except FileNotFoundError:
        pass
    return con


def migrate(con):
    sql = (Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql").read_text()
    con.executescript(sql)
    now = utcnow()
    con.execute("INSERT OR IGNORE INTO settings VALUES ('cooldownDays', ?, ?)", (json.dumps(90), now))
    con.commit()
