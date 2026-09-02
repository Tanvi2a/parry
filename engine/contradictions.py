"""L2 -- the contradiction miner, caged.

The LLM's one job: read the transcript, return statements that contradict
the cardholder's claim, as structured exhibits. Then the cage bars:
  - pydantic validates the shape
  - every quote must be an EXACT substring of a real message
  - ts and sender must match that same message
Failures are dropped (kept visible in `dropped`). The count of VERIFIED
exhibits is the only thing the decision layer ever sees.

  python -m engine.contradictions disp_0015    mine + pretty-print one case
"""
import json
import os
import pathlib
import sys

from pydantic import BaseModel, ValidationError

PROMPT_VERSION = "v1"
CACHE_DIR = pathlib.Path("data/cache/l2") / PROMPT_VERSION

TYPES = ["knowledge_of_order", "possession_admission", "return_request",
         "delivery_acknowledgement", "timeline_conflict", "other"]

CLAIM = {
    "RC-FRAUD": "I did not authorize this transaction / this is not my order",
    "RC-INR": "I never received the item",
    "RC-NAD": "The item was not as described",
    "RC-DUP": "I was charged twice for one purchase",
}


class Exhibit(BaseModel):
    quote: str
    source: str
    ts: int
    type: str
    explanation: str = ""


def build_prompt(cf):
    d, o, s = cf["dispute"], cf["order"], cf["shipment"]
    msgs = cf["chat"]["messages"] if cf["chat"] else []
    facts = dict(
        cardholder_claim=CLAIM[d["reason_code"]],
        reason_code=d["reason_code"],
        item=o["items"][0]["name"],
        delivered_at=s["delivered_at"] if s else None,
        dispute_created_at=d["created_at"],
    )
    return (
        "You are an evidence analyst preparing a chargeback representment.\n"
        f"CASE FACTS: {json.dumps(facts)}\n"
        "Below is the merchant's support-chat transcript. Find customer "
        "statements that CONTRADICT the cardholder's claim above.\n"
        "STRICT RULES:\n"
        "- quote: copied EXACTLY, character-for-character, as a substring "
        "of one message's text. Do not paraphrase, trim words, or fix "
        "spelling.\n"
        "- ts and source: copied from that same message.\n"
        f"- type: one of {TYPES}.\n"
        "- If nothing contradicts the claim, return an empty list.\n"
        'Respond ONLY with JSON: {"exhibits": [{"quote": "...", '
        '"source": "...", "ts": 0, "type": "...", "explanation": "..."}]}\n'
        f"TRANSCRIPT_JSON:{json.dumps(dict(messages=msgs))}"
    )


def _parse(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.startswith("json") else text
    data = json.loads(text)
    return data.get("exhibits", [])


def verify(exhibits, messages):
    """The bar that makes hallucinated evidence structurally impossible."""
    kept, dropped = [], []
    for e in exhibits:
        try:
            ex = Exhibit(**e)
        except ValidationError as err:
            dropped.append(dict(raw=e, reason=f"schema: {err.errors()[0]['msg']}"))
            continue
        match = next((m for m in messages
                      if ex.quote in m["text"] and m["ts"] == ex.ts
                      and m["sender"] == ex.source), None)
        if match is None:
            dropped.append(dict(raw=ex.model_dump(),
                                reason="no message contains this exact "
                                       "quote with matching ts + sender"))
        else:
            kept.append(ex.model_dump())
    return kept, dropped


def mine(con, dispute_id, provider, force=False):
    """Returns the cached-or-fresh verified mining result for one case."""
    from engine.retrieve import case_file
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{dispute_id}.json"
    if path.exists() and not force:
        return json.loads(path.read_text()), True
    cf = case_file(con, dispute_id)
    if (cf is None or cf["order"] is None
            or not (cf["chat"] and cf["chat"]["messages"])):
        result = dict(dispute_id=dispute_id, prompt_version=PROMPT_VERSION,
                      model="none", contradiction_count=0, exhibits=[],
                      dropped=[], raw="",
                      note="no transcript or linked records -- nothing to read")
        path.write_text(json.dumps(result, indent=2))
        return result, False
    msgs = cf["chat"]["messages"]
    raw = provider.complete(build_prompt(cf))
    try:
        exhibits = _parse(raw)
    except (json.JSONDecodeError, AttributeError):
        exhibits = []
    kept, dropped = verify(exhibits, msgs)
    result = dict(dispute_id=dispute_id, prompt_version=PROMPT_VERSION,
                  model=provider.model, contradiction_count=len(kept),
                  exhibits=kept, dropped=dropped, raw=raw)
    path.write_text(json.dumps(result, indent=2))
    return result, False


def cached_count(dispute_id):
    """What the decision layer reads. PARRY_NO_L2=1 mutes it (ablation)."""
    if os.environ.get("PARRY_NO_L2") == "1":
        return 0
    path = CACHE_DIR / f"{dispute_id}.json"
    if not path.exists():
        return 0
    return json.loads(path.read_text()).get("contradiction_count", 0)


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import db
    from engine.llm import get_provider
    provider, _ = get_provider()
    con = db.connect()
    res, from_cache = mine(con, sys.argv[1], provider,
                           force="--force" in sys.argv)
    src = "cache" if from_cache else f"live ({res['model']})"
    print(f"\n{res['dispute_id']}  ·  source: {src}  ·  "
          f"verified exhibits: {res['contradiction_count']}")
    for e in res["exhibits"]:
        print(f"  [{e['type']}] \"{e['quote']}\"")
        print(f"      -- {e['source']} @ ts {e['ts']}  ({e['explanation']})")
    for dr in res["dropped"]:
        print(f"  DROPPED: {dr['reason']}")
