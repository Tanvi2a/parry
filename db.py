"""SQLite setup. Phase 1: two tables. The other nine arrive in Phase 2."""
import sqlite3
import pathlib

DB = pathlib.Path("data/out/parry.db")

DDL = """
CREATE TABLE IF NOT EXISTS disputes(
  id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, currency TEXT,
  reason_code TEXT, respond_by TEXT, status TEXT, raised_at TEXT);
CREATE TABLE IF NOT EXISTS audit_events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT,
  action TEXT, payload_hash TEXT, prev_hash TEXT);
"""


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(DDL)
    return con
