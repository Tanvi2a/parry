"""Fake Razorpay: rings the webhook doorbell with one random dispute,
shaped exactly like the real dispute entity (unix timestamps, paise)."""
import datetime as dt
import random

import requests

now = int(dt.datetime.now(dt.timezone.utc).timestamp())
rc = random.choice(["RC-FRAUD", "RC-INR", "RC-NAD", "RC-DUP"])
d = {"id": f"disp_live{random.randrange(10**4):04d}",
     "entity": "dispute",
     "payment_id": f"pay_live{random.randrange(10**4):04d}",
     "amount": random.randrange(50000, 800001),
     "currency": "INR",
     "amount_deducted": 0,
     "reason_code": rc,
     "reason_description": "simulated dispute",
     "respond_by": now + 7 * 86400,
     "status": "open",
     "phase": "chargeback",
     "created_at": now}
print(requests.post("http://127.0.0.1:8000/webhook/dispute", json=d).json())
