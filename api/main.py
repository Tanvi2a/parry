"""The receptionist: answers the webhook, validates, stores, decides, logs."""
import time

from fastapi import FastAPI

from api.audit import log
from db import connect
from engine.decide import decide
from schemas import Dispute

app = FastAPI(title="Parry")

DISPUTE_COLS = ("id", "entity", "payment_id", "amount", "currency",
                "amount_deducted", "reason_code", "reason_description",
                "respond_by", "status", "phase", "created_at")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook/dispute")
def webhook(d: Dispute):
    con = connect()
    con.execute(
        f"INSERT OR REPLACE INTO disputes({','.join(DISPUTE_COLS)}) "
        f"VALUES({','.join('?' * len(DISPUTE_COLS))})",
        tuple(getattr(d, c) for c in DISPUTE_COLS))
    con.commit()
    result = decide(con, d.id, now=int(time.time()))
    log(con, "parry", f"decision:{d.id}:{result['verdict']}:{result['mode']}")
    return {"case": d.id, **{k: result[k] for k in
                             ("verdict", "p_win", "ev_paise", "mode",
                              "rationale")}}


@app.get("/decision/{dispute_id}")
def decision(dispute_id: str):
    con = connect()
    row = con.execute("SELECT * FROM decisions WHERE dispute_id=?",
                      (dispute_id,)).fetchone()
    if row is None:
        return {"error": "no decision yet"}
    keys = ("dispute_id", "verdict", "p_win", "ev_paise", "mode",
            "detail", "decided_at")
    return dict(zip(keys, row))
