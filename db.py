"""SQLite setup: the merchant's systems in one file. 12 tables.
ground_truth is generator/eval infrastructure ONLY -- the decision engine
never reads it at inference time (that's the whole honesty story)."""
import sqlite3
import pathlib

DB = pathlib.Path("data/out/parry.db")

DDL = """
CREATE TABLE IF NOT EXISTS customers(
  id TEXT PRIMARY KEY, name TEXT, prior_orders INTEGER, device_ids TEXT);
CREATE TABLE IF NOT EXISTS orders(
  id TEXT PRIMARY KEY, customer_id TEXT, items TEXT, amount INTEGER,
  listing_match INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS payments(
  id TEXT PRIMARY KEY, order_id TEXT, method TEXT, status TEXT,
  amount INTEGER, captured_at INTEGER);
CREATE TABLE IF NOT EXISTS auth_log(
  payment_id TEXT PRIMARY KEY, otp_result TEXT, three_ds_result TEXT,
  device_id TEXT, device_known INTEGER, ts INTEGER);
CREATE TABLE IF NOT EXISTS shipments(
  id TEXT PRIMARY KEY, order_id TEXT, carrier TEXT, status TEXT,
  events TEXT, pod_url TEXT, address_match INTEGER, delivered_at INTEGER);
CREATE TABLE IF NOT EXISTS chat_threads(
  id TEXT PRIMARY KEY, customer_id TEXT, order_id TEXT, channel TEXT,
  messages TEXT, return_offered INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS refunds(
  id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, status TEXT,
  ts INTEGER);
CREATE TABLE IF NOT EXISTS disputes(
  id TEXT PRIMARY KEY, entity TEXT, payment_id TEXT, amount INTEGER,
  currency TEXT, amount_deducted INTEGER, reason_code TEXT,
  reason_description TEXT, respond_by INTEGER, status TEXT, phase TEXT,
  created_at INTEGER);
CREATE TABLE IF NOT EXISTS decisions(
  dispute_id TEXT PRIMARY KEY, verdict TEXT, p_win REAL, ev_paise INTEGER,
  mode TEXT, features TEXT, decided_at INTEGER);
CREATE TABLE IF NOT EXISTS packets(
  decision_id TEXT PRIMARY KEY, narrative TEXT, exhibits TEXT,
  html_uri TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS audit_events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT,
  action TEXT, payload_hash TEXT, prev_hash TEXT);
CREATE TABLE IF NOT EXISTS ground_truth(
  dispute_id TEXT PRIMARY KEY, truth TEXT, winnable INTEGER,
  flipped INTEGER, split TEXT);
"""


def connect(db_path=None):
    path = pathlib.Path(db_path) if db_path else DB
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(DDL)
    return con
