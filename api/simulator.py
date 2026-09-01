"""Fake Razorpay webhook.
  python api/simulator.py              -> one random dispute (no linked
                                          records => Parry ABSTAINs to human)
  python api/simulator.py disp_0015    -> replay a seeded dispute with its
                                          full evidence trail (the demo path)
"""
import datetime as dt
import random
import sqlite3
import sys

import requests

URL = "http://127.0.0.1:8000/webhook/dispute"
COLS = ("id", "entity", "payment_id", "amount", "currency",
        "amount_deducted", "reason_code", "reason_description",
        "respond_by", "status", "phase", "created_at")

if len(sys.argv) > 1:
    con = sqlite3.connect("data/out/parry.db")
    row = con.execute("SELECT * FROM disputes WHERE id=?",
                      (sys.argv[1],)).fetchone()
    if row is None:
        raise SystemExit(f"no such seeded dispute: {sys.argv[1]}")
    d = dict(zip(COLS, row))
else:
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    d = {"id": f"disp_live{random.randrange(10**4):04d}",
         "entity": "dispute",
         "payment_id": f"pay_live{random.randrange(10**4):04d}",
         "amount": random.randrange(50000, 800001),
         "currency": "INR", "amount_deducted": 0,
         "reason_code": random.choice(["RC-FRAUD", "RC-INR",
                                       "RC-NAD", "RC-DUP"]),
         "reason_description": "simulated dispute",
         "respond_by": now + 7 * 86400, "status": "open",
         "phase": "chargeback", "created_at": now}
print(requests.post(URL, json=d).json())
