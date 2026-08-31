"""Single source of truth for data shapes. Mirrors Razorpay's dispute entity
(razorpay.com/docs/api/disputes): amounts in currency subunits (paise, int),
timestamps as Unix epoch integers."""
from pydantic import BaseModel


class Dispute(BaseModel):
    id: str                      # disp_xxxxxx
    entity: str = "dispute"
    payment_id: str              # pay_xxxxxx
    amount: int                  # paise, never floats: Rs 2,499 -> 249900
    currency: str = "INR"
    amount_deducted: int = 0     # 0 unless dispute is lost
    reason_code: str             # RC-FRAUD | RC-INR | RC-NAD | RC-DUP
    reason_description: str = ""
    respond_by: int              # unix ts; past this, Parry may never submit
    status: str = "open"         # open|under_review|won|lost|closed
    phase: str = "chargeback"
    created_at: int              # unix ts
