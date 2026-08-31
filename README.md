# Parry — AI chargeback defense agent
Razorpay Buildathon 2026 · Track 02 (AI Risk Manager)

> Auto-responders fight what they can. Parry fights what it should.

**Status: Phase 1 — walking skeleton.** Webhook -> SQLite -> stub decision ->
hash-chained audit -> bare UI. See BUILD_PLAN.md for all phases.

## Quickstart (Phase 1)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic requests
uvicorn api.main:app --reload --port 8000
# second terminal:
python api/simulator.py        # fires one fake dispute
```
Interactive API docs: http://127.0.0.1:8000/docs
Dashboard (needs `pip install streamlit pandas`): `streamlit run ui/app.py`
