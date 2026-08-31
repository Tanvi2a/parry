"""The receptionist: answers the webhook, validates, stores, decides, logs."""
from fastapi import FastAPI
from schemas import Dispute
from db import connect
from engine.decide import decide
from api.audit import log

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
    result = decide(d)
    log(con, "parry", f"decision:{d.id}:{result['verdict']}")
    return {"case": d.id, **result}
