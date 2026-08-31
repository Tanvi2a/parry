"""Step 3: corrupt reality a little, AFTER truth and artifacts exist.
Noise is applied BEFORE labeling, so a case that loses its POD to noise
genuinely becomes unwinnable -- evidence, not truth, is what you fight with."""
import json

HOUR = 3600


def _typo(rng, text):
    words = text.split()
    if len(words) < 3:
        return text
    j = rng.randrange(len(words))
    w = words[j]
    if len(w) > 3:
        k = rng.randrange(len(w) - 1)
        words[j] = w[:k] + w[k + 1] + w[k] + w[k + 2:]
    return " ".join(words)


def apply(rng, cases, anchor):
    n = len(cases)
    # 10% of delivered shipments lose their tracking trail + POD
    delivered = [c for c in cases if c["shipment"]["status"] == "delivered"]
    for c in rng.sample(delivered, max(1, int(0.10 * len(delivered)))):
        c["shipment"]["pod_url"] = None
        c["shipment"]["events"] = json.dumps(["picked_up"])
        c["noise_pod_lost"] = True
    # sloppy spelling in ~25% of customer messages
    for c in cases:
        msgs = json.loads(c["chat"]["messages"])
        for m in msgs:
            if m["sender"] == "customer" and rng.random() < 0.25:
                m["text"] = _typo(rng, m["text"])
        c["chat"]["messages"] = json.dumps(msgs)
    # timestamp jitter on dispute creation (+/- up to 3h)
    for c in cases:
        c["dispute"]["created_at"] += rng.randint(-3, 3) * HOUR
    # exactly 2 near-deadline cases and 1 past-deadline case
    picks = rng.sample(range(n), 3)
    for idx in picks[:2]:
        cases[idx]["dispute"]["respond_by"] = anchor + rng.randint(6, 30) * HOUR
    cases[picks[2]]["dispute"]["respond_by"] = anchor - rng.randint(12, 48) * HOUR
    return cases
