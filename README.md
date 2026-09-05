# Parry — the AI chargeback defense agent

> **Auto-responders fight what they can. Parry fights what it should.**

Razorpay Buildathon 2026 · Track 02 — AI Risk Manager · solo build


## What it is

A dispute arrives (Razorpay-shaped webhook) → Parry pulls every linked record → decides **FIGHT / ACCEPT / ABSTAIN** with a calibrated win probability and an expected-value rationale → if FIGHT, generates the representment packet → submits (simulated) → writes every action to an append-only, hash-chained audit log.

Strictly defensive: Parry can only respond to disputes already filed against the merchant. It has no offensive surface. It is named after fencing's defensive move.

## Why this, when auto-responders already exist

Chargeflow, Justt, and Razorpay's own Dispute Responder (Agent Studio, beta) all fetch evidence and file responses. What none of them publish is the **judgment layer**: calibrated p(win), expected-value-gated *selection* of which disputes to fight, an abstain band for the ambiguous middle, and **precision, recall and false-positive cost measured on a frozen held-out set** — which is precisely what this track's bar asks for. Parry is that layer.

## Results — measured once, on a frozen held-out set

200 causally generated synthetic disputes · 140 train / 60 held-out · split frozen (SHA-256 `787b0df8a0e521d0…`) before evaluation · cost-to-fight ₹650.

| 60 held-out cases | fought | precision | recall | FP cost | **net ₹** |
|---|---|---|---|---|---|
| **Parry** | 29 | **0.862** | 0.806 | **₹2,600** | **+₹43,119** |
| Parry −L2 (LLM feature muted) | 30 | 0.833 | 0.806 | ₹3,250 | +₹42,368 |
| Fight everything | 60 | 0.517 | 1.000 | ₹18,850 | +₹39,261 |
| Accept everything | 0 | — | 0 | ₹0 | ₹0 |

**Reading it honestly.** Parry nets more than either naive policy while burning one-seventh of fight-all's false-positive cost. The ablation row is the LLM's contribution *as a number*: with the contradiction feature muted, Parry fights exactly one more case — and loses it. The reader made Parry pickier, not trigger-happier. **Recall missed our 0.93 planning target** — 6 winnable disputes weren't fought, 2 of them correctly routed to human review by the abstain band. Reported as measured; the bar says honest metrics. Of the 29 fights, 23 cleared all three auto-submit floors (p ≥ 0.75, amount ≤ ₹5,000, completeness ≥ 0.8); 6 went to one-click human review.

## Architecture — the LLM never touches the money math

```
webhook (Razorpay-shaped) → SQLite case file (deterministic joins)
   → L1  RULES      weighted evidence checklist per reason code → completeness c ∈ [0,1]
   → L2  LANGUAGE   Gemini reads the chat → cited exhibits, each quote VERIFIED as an
                    exact substring of a real message with matching timestamp + sender
   → L3  ARITHMETIC 5-feature logistic p(win) → FIGHT iff p × amount > cost-to-fight
   → gates: abstain band · completeness floor · ₹5k auto cap · deadline lockout · kill switch
   → packet (Razorpay evidence slots) · append-only hash-chained audit log · dashboard
```

The LLM contributes **one integer** (verified contradiction count) to a five-feature model — coefficients small enough to print (see Metrics page). Every LLM response is cached in-repo with its raw text, so judges can audit what the model said versus what survived verification. Full diagrams in the PRD (§7–§11).

**The India edge.** Every card payment here is OTP-authenticated by RBI mandate; a clean OTP log on a known device shifts fraud liability toward the issuer. Parry treats the auth log as Exhibit A for "unauthorized" claims — the strongest single signal after evidence completeness.

## Run it — no API key required

```bash
git clone https://github.com/Tanvi2a/parry && cd parry
./run.sh
```

That creates a venv, installs, starts the API on :8000, replays a seeded dispute through the webhook, and opens the dashboard on :8501. Everything needed ships in the repo: `data/out/parry.db`, the verified L2 cache (`data/cache/l2/`), both model bundles, `eval.json` and the split manifest. Then walk the demo:

1. **Queue** — sorted by deadline; SLA colors are live.
2. **Case `disp_0015`** — "item not received," but the verified exhibit glows in the transcript: *"bhai order aa gaya but smartwatch ka siez chhota hai, exchange kaise karu?"* (typo and all — verbatim is the rule). FIGHT · p 0.76 · EV +₹2,240 · auto. Generate packet → download → Submit.
3. **A genuine-fraud case** (any ACCEPT with reason RC-FRAUD) — failed OTP, unknown device: ACCEPT, negative EV. Restraint is the product.
4. **`disp_0011`** — Submit → *deadline lockout, no override exists*. Flip the kill switch → every submit halts, and the flip itself is in the audit log.
5. **Audit** — the hash chain is re-verified on every page load. **Metrics** — coefficients, calibration, the frozen eval.

Reproduce the dataset and the eval yourself:

```bash
python -m data.generator.generate --n 200 --seed 42   # byte-identical DB; prints content SHA-256
python -m engine.run_eval                              # refuses to run if the split changed
python -m pytest tests/ -q                             # 13 passed
```

Re-mining the L2 cache (`python -m engine.run_l2`) is the only step that needs a `GEMINI_API_KEY` in `.env`; free-tier daily quotas are per model — see `config/parry.yaml`.

## Honest limitations

- **Synthetic data.** Ground truth is sampled first, artifacts generated to match, noise injected, labels computed from four printable network rules on post-noise evidence with a 6% adjudication flip. The label never touches an LLM. It is still a world we built; the methodology, not the absolute numbers, is the claim. In production the same five features retrain on real dispute outcomes.
- **60 held-out cases** is a small test set; one decision moves precision by ~3 points. The ablation delta (one fight) is real but modest.
- **Mixed mining models.** ~20 cases were mined on `gemini-3.5-flash` before its 20/day free-tier quota; the rest on `gemini-3.5-flash-lite`. Each cache file records its model. The substring verifier is the quality gate regardless.
- **Recall 0.81** vs a 0.93 target — see Results.
- **Four reason codes**, card-network representment only; UPI dispute rails (URCS/UDIR) are out of scope.
- Submission is simulated; the packet is keyed to Razorpay's contest-API evidence slots so the swap is a payload mapping.

## Privacy in production

Today: 100% synthetic, zero real PII by construction. In production: deterministic PII redaction before any model call → zero-data-retention, in-region inference to satisfy RBI data-localization and DPDP → long-term, a self-hosted open-weight miner fine-tuned on real outcomes.

## Repo map

```
api/          webhook, simulator (replays seeded disputes), hash-chained audit
engine/       retrieve · checklists (L1) · llm + contradictions (L2) · features · model · decide (L3 + gates) · run_eval
data/         generator (truth-first) · out/ (db, models, eval, manifest) · cache/l2 (verified LLM exhibits + raw)
packet/       representment builder → HTML keyed to Razorpay evidence slots
ui/           Streamlit dashboard: queue · case · metrics · audit
tests/        13 tests — exact checklist scores, generator determinism, gate invariants, the verifier cage
docs/         pitch deck · PRD with diagrams · video script
```

Build history is tagged phase by phase: `p1-skeleton` → `p2-data` → `p3-checklists` → `p4-llm-free` (a complete Parry with zero LLM calls) → `p5-caged-llm` → `p6-face` → `p7-frozen`.
