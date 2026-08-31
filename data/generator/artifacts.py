"""Step 2: generate every merchant-system artifact CONSISTENT with the truth.
All timestamps are unix ints relative to a fixed anchor (so the dataset is
byte-reproducible AND the deadlines are 'live' relative to demo day)."""
import json

DAY, HOUR, MIN = 86400, 3600, 60

FIRST = ["Aarav", "Priya", "Rohan", "Sneha", "Kabir", "Ananya", "Vikram",
         "Isha", "Aditya", "Meera", "Farhan", "Divya", "Arjun", "Pooja"]
LAST = ["Sharma", "Patel", "Reddy", "Khan", "Iyer", "Gupta", "Das",
        "Mehta", "Nair", "Singh", "Bose", "Kulkarni"]
ITEMS = [("cotton kurta", 89900), ("bluetooth earbuds", 249900),
         ("yoga mat", 74900), ("banarasi saree", 419900),
         ("running shoes", 329900), ("mixer grinder", 289900),
         ("laptop backpack", 159900), ("ceramic dinner set", 219900),
         ("smartwatch", 379900), ("table lamp", 99900),
         ("phone case", 59900), ("air fryer", 549900)]
CARRIERS = ["Delhivery", "BlueDart", "Ekart", "XpressBees", "DTDC"]


def build_case(rng, i, truth, rc, anchor):
    """Returns a dict of rows for one dispute case. Truth drives every flag."""
    c = {"i": i, "truth": truth, "rc": rc}
    cust_id, ord_id = f"cust_{i:04d}", f"ord_{i:04d}"
    pay_id, disp_id = f"pay_{i:04d}", f"disp_{i:04d}"

    # --- timeline skeleton ---
    disp_created = anchor - rng.randint(1, 5) * DAY - rng.randint(0, 20) * HOUR
    order_created = disp_created - rng.randint(12, 35) * DAY
    captured_at = order_created + rng.randint(2, 12) * MIN
    auth_ts = captured_at - rng.randint(20, 90)
    respond_by = disp_created + rng.randint(7, 10) * DAY

    # --- customer profile (history depends on truth) ---
    if truth == "friendly_fraud":
        prior = rng.randint(2, 9)
    elif truth == "genuine_fraud":
        prior = rng.randint(0, 1)
    else:
        prior = rng.randint(0, 6)
    known_devices = [f"dev_{i:04d}a"] + (
        [f"dev_{i:04d}b"] if prior >= 3 else [])
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    c["customer"] = dict(id=cust_id, name=name, prior_orders=prior,
                         device_ids=json.dumps(known_devices))

    # --- order ---
    item, price = rng.choice(ITEMS)
    qty = 1 if price > 200000 else rng.randint(1, 2)
    amount = price * qty
    listing_match = 0 if (truth == "merchant_error" and rc == "RC-NAD") else 1
    c["order"] = dict(id=ord_id, customer_id=cust_id,
                      items=json.dumps([{"name": item, "qty": qty,
                                         "price_paise": price}]),
                      amount=amount, listing_match=listing_match,
                      created_at=order_created)
    c["item"] = item

    # --- payment + auth (the India edge lives here) ---
    method = rng.choice(["credit_card", "credit_card", "debit_card"])
    c["payments"] = [dict(id=pay_id, order_id=ord_id, method=method,
                          status="captured", amount=amount,
                          captured_at=captured_at)]
    if truth == "genuine_fraud":
        otp = "passed" if rng.random() < 0.45 else "failed_retry"
        device, device_known = f"dev_new_{i:04d}", 0
    elif truth == "friendly_fraud":
        otp, device, device_known = "passed", known_devices[0], 1
    elif truth == "ambiguous" and rc == "RC-FRAUD":
        otp = rng.choice(["passed", "failed_retry"])
        device_known = rng.randint(0, 1)
        device = known_devices[0] if device_known else f"dev_new_{i:04d}"
    else:
        otp, device, device_known = "passed", known_devices[0], 1
    c["auth"] = dict(payment_id=pay_id, otp_result=otp,
                     three_ds_result=otp, device_id=device,
                     device_known=device_known, ts=auth_ts)

    # --- shipment ---
    delivered_at = order_created + rng.randint(2, 6) * DAY
    if truth == "delivery_failure":
        status = rng.choice(["in_transit", "failed", "rto"])
        pod, addr_match, delivered_at = None, 1, None
        events = ["picked_up", "in_transit"]
    else:
        status, pod = "delivered", f"pod/{ord_id}.jpg"
        addr_match = 1
        events = ["picked_up", "in_transit", "out_for_delivery", "delivered"]
    c["shipment"] = dict(id=f"shp_{i:04d}", order_id=ord_id,
                         carrier=rng.choice(CARRIERS), status=status,
                         events=json.dumps(events), pod_url=pod,
                         address_match=addr_match, delivered_at=delivered_at)
    c["delivered_at"] = delivered_at

    # --- duplicate-charge cases need a second payment or order ---
    c["dup_two_orders"] = 0
    c["refunds"] = []
    if rc == "RC-DUP":
        if truth == "merchant_error":     # true duplicate: 1 order, 2 charges
            pay2 = f"pay_{i:04d}d"
            c["payments"].append(dict(id=pay2, order_id=ord_id,
                                      method=method, status="captured",
                                      amount=amount,
                                      captured_at=captured_at + 3 * MIN))
            if rng.random() < 0.5:        # sometimes already refunded
                c["refunds"].append(dict(id=f"rfnd_{i:04d}", payment_id=pay2,
                                         amount=amount, status="processed",
                                         ts=captured_at + 2 * DAY))
        else:                             # two genuine orders, same day
            c["dup_two_orders"] = 1
            ord2, pay2 = f"ord_{i:04d}b", f"pay_{i:04d}b"
            item2, price2 = rng.choice(ITEMS)
            c["order2"] = dict(id=ord2, customer_id=cust_id,
                               items=json.dumps([{"name": item2, "qty": 1,
                                                  "price_paise": price2}]),
                               amount=price2, listing_match=1,
                               created_at=order_created + 40 * MIN)
            c["payments"].append(dict(id=pay2, order_id=ord2, method=method,
                                      status="captured", amount=price2,
                                      captured_at=order_created + 42 * MIN))

    # --- dispute (Razorpay-shaped) ---
    from data.generator.truth_sampler import REASON_DESCRIPTION
    c["dispute"] = dict(id=disp_id, entity="dispute", payment_id=pay_id,
                        amount=amount, currency="INR", amount_deducted=0,
                        reason_code=rc,
                        reason_description=REASON_DESCRIPTION[rc],
                        respond_by=respond_by, status="open",
                        phase="chargeback", created_at=disp_created)
    return c
