"""The receptionist: answers the webhook, validates, stores, decides, logs."""
from fastapi import FastAPI
from schemas import Dispute
from db import connect
from engine.decide import decide
from api.audit import log

app = FastAPI(title="Parry")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook/dispute")
def webhook(d: Dispute):
    con = connect()
    con.execute("INSERT OR REPLACE INTO disputes VALUES(?,?,?,?,?,?,?,?)",
                (d.id, d.payment_id, d.amount, d.currency, d.reason_code,
                 str(d.respond_by), d.status, str(d.raised_at)))
    con.commit()
    result = decide(d)
    log(con, "parry", f"decision:{d.id}:{result['verdict']}")
    return {"case": d.id, **result}