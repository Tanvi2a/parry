"""Fake Razorpay: rings the webhook doorbell with one random dispute."""
import requests
import random
import datetime as dt

now = dt.datetime.now(dt.timezone.utc)
d = {"id": f"disp_{random.randrange(10**6):06d}",
     "payment_id": f"pay_{random.randrange(10**6):06d}",
     "amount": random.randrange(50000, 800001),  # Rs 500 - Rs 8,000 in paise
     "reason_code": random.choice(["RC-FRAUD", "RC-INR", "RC-NAD", "RC-DUP"]),
     "respond_by": (now + dt.timedelta(days=7)).isoformat(),
     "raised_at": now.isoformat()}
print(requests.post("http://127.0.0.1:8000/webhook/dispute", json=d).json())
