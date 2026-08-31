"""Step 4: the label. winnable = truth-consistent evidence satisfying
network rules -- computed from post-noise artifacts, never from an LLM.
A 6% random flip simulates noisy issuer adjudication."""

FLIP_P = 0.06


def _rule_winnable(c):
    rc, sh, auth = c["rc"], c["shipment"], c["auth"]
    if rc == "RC-FRAUD":
        # India edge: clean OTP on a known device => liability shifted
        return auth["otp_result"] == "passed" and auth["device_known"] == 1
    if rc == "RC-INR":
        return (sh["status"] == "delivered" and sh["pod_url"] is not None
                and sh["address_match"] == 1
                and (sh["delivered_at"] or 0) < c["dispute"]["created_at"])
    if rc == "RC-NAD":
        return (c["order"]["listing_match"] == 1
                and c["chat"]["return_offered"] == 1)
    if rc == "RC-DUP":
        return c["dup_two_orders"] == 1
    return False


def label(rng, c):
    base = _rule_winnable(c)
    flipped = rng.random() < FLIP_P
    c["winnable"] = int(base != flipped)   # flip inverts the rule outcome
    c["flipped"] = int(flipped)
    return c
