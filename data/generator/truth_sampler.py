"""Step 1 of causal generation: sample the hidden TRUTH first.
Everything downstream (artifacts, chats, labels) is conditioned on it."""

TRUTH_MIX = [
    ("friendly_fraud", 0.35),   # legit, authenticated txn disputed anyway
    ("genuine_fraud", 0.25),    # actually-stolen instrument
    ("delivery_failure", 0.15), # merchant/carrier really failed to deliver
    ("merchant_error", 0.15),   # wrong item / duplicate charge etc.
    ("ambiguous", 0.10),        # genuinely murky
]

# Which reason code does a dispute with this truth arrive under?
RC_GIVEN_TRUTH = {
    "friendly_fraud":  [("RC-FRAUD", 0.45), ("RC-INR", 0.35),
                        ("RC-NAD", 0.15), ("RC-DUP", 0.05)],
    "genuine_fraud":   [("RC-FRAUD", 1.0)],
    "delivery_failure": [("RC-INR", 1.0)],
    "merchant_error":  [("RC-NAD", 0.5), ("RC-DUP", 0.5)],
    "ambiguous":       [("RC-NAD", 0.6), ("RC-INR", 0.2), ("RC-FRAUD", 0.2)],
}

REASON_DESCRIPTION = {
    "RC-FRAUD": "Cardholder claims the transaction was not authorized",
    "RC-INR": "Cardholder claims the item was not received",
    "RC-NAD": "Cardholder claims the item was not as described",
    "RC-DUP": "Cardholder claims a duplicate charge",
}


def _weighted(rng, pairs):
    r, acc = rng.random(), 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def sample_truth(rng):
    return _weighted(rng, TRUTH_MIX)


def sample_reason_code(rng, truth):
    return _weighted(rng, RC_GIVEN_TRUTH[truth])
