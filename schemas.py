"""Single source of truth for data shapes. Mirrors Razorpay's dispute entity."""
from pydantic import BaseModel
from datetime import datetime


class Dispute(BaseModel):
    id: str                  # disp_xxxxxx
    payment_id: str          # pay_xxxxxx
    amount: int              # paise, never floats: Rs 2,499 -> 249900
    currency: str = "INR"
    reason_code: str         # RC-FRAUD | RC-INR | RC-NAD | RC-DUP
    respond_by: datetime     # deadline; past this, Parry may never submit
    status: str = "open"
    raised_at: datetime
