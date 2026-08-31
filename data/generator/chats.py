"""Step 2b: support-chat transcripts, template-based (Phase 5 swaps in LLM
prose for variety -- facts stay fixed, only the voice changes).
The smoking-gun contradictions for friendly fraud are planted HERE."""
import json

DAY, HOUR = 86400, 3600


def _msgs(rng, case, anchor):
    truth, rc, item = case["truth"], case["rc"], case["item"]
    delivered = case.get("delivered_at")
    t0 = delivered or case["order"]["created_at"] + 3 * DAY
    out = []

    def add(sender, text, ts):
        out.append({"sender": sender, "text": text, "ts": int(ts)})

    if truth == "friendly_fraud" and rc == "RC-INR":
        v = rng.choice([
            ("bhai order aa gaya but {item} ka size chhota hai, "
             "exchange kaise karu?",
             "Sorry to hear that! We can offer an exchange or store credit."),
            ("received the {item} yesterday, quality theek hai but colour "
             "photo se different lag raha", 
             "We're sorry! You can return it within 7 days for a refund."),
            ("got my parcel today. can I return {item}? fitting is not good",
             "Of course — we have initiated a return pickup for you."),
        ])
        add("customer", v[0].format(item=item), t0 + rng.randint(1, 2) * DAY)
        add("support", v[1], t0 + rng.randint(1, 2) * DAY + HOUR)
        case["return_offered"] = 1
    elif truth == "friendly_fraud" and rc == "RC-FRAUD":
        v = rng.choice([
            "when will my {item} arrive? ordered last week",
            "please expedite delivery of my {item}, need it for a function",
            "tracking not updating for my {item} order, pls check",
        ])
        add("customer", v.format(item=item),
            case["order"]["created_at"] + rng.randint(1, 3) * DAY)
        add("support", "Your order is on the way and will arrive shortly!",
            case["order"]["created_at"] + rng.randint(1, 3) * DAY + HOUR)
        case["return_offered"] = 0
    elif truth == "friendly_fraud" and rc == "RC-NAD":
        add("customer", f"the {item} is fine but I found it cheaper "
            "elsewhere, can you price match?", t0 + DAY)
        add("support", "We don't price match, but you may return within "
            "7 days for a full refund.", t0 + DAY + HOUR)
        case["return_offered"] = 1
    elif truth == "genuine_fraud":
        add("customer", "I did not make this transaction. This is not my "
            "order. Please reverse it immediately.",
            case["dispute"]["created_at"] - rng.randint(1, 24) * HOUR)
        add("support", "We understand your concern and are looking into it.",
            case["dispute"]["created_at"] - rng.randint(0, 12) * HOUR)
        case["return_offered"] = 0
    elif truth == "delivery_failure":
        add("customer", f"where is my {item}?? tracking stuck since 4 days",
            case["order"]["created_at"] + 5 * DAY)
        add("support", "Apologies — there is a delay with the courier. "
            "We are escalating.", case["order"]["created_at"] + 5 * DAY + HOUR)
        case["return_offered"] = 0
    elif truth == "merchant_error" and rc == "RC-NAD":
        add("customer", f"you sent me the WRONG item, I ordered {item} and "
            "got something else entirely", t0 + DAY)
        add("support", "We sincerely apologise for the mix-up. We can "
            "arrange a replacement.", t0 + DAY + HOUR)
        case["return_offered"] = 1
    elif rc == "RC-DUP":
        add("customer", "I have been charged twice for my order, please "
            "check and refund the extra amount",
            case["payments"][0]["captured_at"] + DAY)
        add("support", "Thanks for flagging — our payments team is "
            "reviewing the duplicate charge.",
            case["payments"][0]["captured_at"] + DAY + HOUR)
        case["return_offered"] = 0
    else:  # ambiguous, misc
        add("customer", f"not happy with the {item}, want to discuss",
            t0 + rng.randint(1, 3) * DAY)
        add("support", "Sorry to hear that! Could you share more details?",
            t0 + rng.randint(1, 3) * DAY + HOUR)
        case["return_offered"] = rng.randint(0, 1)
    return out


def build_chat(rng, case, anchor):
    msgs = _msgs(rng, case, anchor)
    case["chat"] = dict(id=f"cht_{case['i']:04d}",
                        customer_id=case["customer"]["id"],
                        order_id=case["order"]["id"],
                        channel=rng.choice(["web", "whatsapp", "email"]),
                        messages=json.dumps(msgs),
                        return_offered=case.get("return_offered", 0),
                        created_at=msgs[0]["ts"] if msgs else anchor)
    return case
