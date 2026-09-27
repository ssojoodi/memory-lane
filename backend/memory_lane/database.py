import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .paths import database_path
from .storage import open_private_database


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect(path=None):
    con = open_private_database(path or database_path())
    try:
        configure(con)
        migrate(con)
        return con
    except BaseException:
        con.close()
        raise


def configure(con):
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")


def migrate(con):
    sql = (Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql").read_text()
    con.executescript(sql)
    now = utcnow()
    con.execute("INSERT OR IGNORE INTO settings VALUES ('cooldownDays', ?, ?)", (json.dumps(90), now))
    con.commit()
