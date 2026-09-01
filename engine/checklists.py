"""L1 -- evidence-completeness checklists. Pure functions over the case
file: no randomness, no LLM, no ground_truth. Each reason code has a
weighted checklist of what a card-network representment demands;
completeness = weighted fraction of favorable evidence PRESENT.

This is the merchant-side mirror of the labeler: the labeler asks
'would this win?', the checklist asks 'do we hold the documents?'."""


def _fraud(cf):
    a, cu, s = cf["auth"], cf["customer"], cf["shipment"]
    return [
        ("otp_passed", 0.35, a["otp_result"] == "passed"),
        ("device_known", 0.25, a["device_known"] == 1),
        ("prior_orders_2plus", 0.20, cu["prior_orders"] >= 2),
        ("three_ds_passed", 0.10, a["three_ds_result"] == "passed"),
        ("delivery_evidence", 0.10,
         bool(s and s["status"] == "delivered" and s["pod_url"])),
    ]


def _inr(cf):
    s, d = cf["shipment"], cf["dispute"]
    delivered = bool(s and s["status"] == "delivered")
    return [
        ("delivered_status", 0.30, delivered),
        ("pod_present", 0.25, bool(s and s["pod_url"])),
        ("address_match", 0.15, bool(s and s["address_match"] == 1)),
        ("delivered_before_dispute", 0.15,
         bool(s and s["delivered_at"]
              and s["delivered_at"] < d["created_at"])),
        ("full_tracking_trail", 0.15,
         bool(s and "delivered" in s["events"])),
    ]


def _nad(cf):
    o, ch, s = cf["order"], cf["chat"], cf["shipment"]
    return [
        ("listing_match", 0.30, o["listing_match"] == 1),
        ("return_offered", 0.30, bool(ch and ch["return_offered"] == 1)),
        ("delivered_with_pod", 0.20,
         bool(s and s["status"] == "delivered" and s["pod_url"])),
        ("chat_present", 0.20, bool(ch and ch["messages"])),
    ]


def _dup(cf):
    sibs, o, s = cf["siblings"], cf["order"], cf["shipment"]
    distinct = [x for x in sibs if x["order_id"] != o["id"]]
    items = {i["name"] for i in o["items"]}
    differing = [x for x in distinct
                 if {i["name"] for i in x["sib_items"]} != items
                 or x["amount"] != cf["payment"]["amount"]]
    return [
        ("sibling_payment_found", 0.20, len(sibs) > 0),
        ("distinct_order_ids", 0.40, len(distinct) > 0),
        ("items_or_amounts_differ", 0.20, len(differing) > 0),
        ("delivery_evidence", 0.20,
         bool(s and s["status"] == "delivered" and s["pod_url"])),
    ]


CHECKS = {"RC-FRAUD": _fraud, "RC-INR": _inr, "RC-NAD": _nad, "RC-DUP": _dup}


def completeness(cf):
    """Returns (score in [0,1], breakdown list of dicts)."""
    checks = CHECKS[cf["dispute"]["reason_code"]](cf)
    total = sum(w for _, w, _ in checks)
    score = sum(w for _, w, ok in checks if ok) / total
    breakdown = [dict(check=n, weight=w, passed=bool(ok))
                 for n, w, ok in checks]
    return round(score, 4), breakdown
