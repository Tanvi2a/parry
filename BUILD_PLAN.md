# Parry — build plan (solo, ~32-38h)
Tracer-bullet rule: Phase 1 creates a fake-but-complete loop; every later
phase replaces one fake part with a real one. Demoable after every phase.

- **P0 · Prep (2h, pre-event).** Gemini key (fresh Google project, billing
  NEVER enabled), repo, venv, full requirements install, read Razorpay
  Disputes API + Visa CE 3.0 fields, check event rules + sponsor credits.
  Done: test Gemini call returns JSON.
- **P1 · Walking skeleton (2h).** schemas, 2-table db, hardcoded decide(),
  hash-chained audit, FastAPI webhook, simulator, bare Streamlit.
  Done: simulator returns verdict JSON; audit chain grows.
- **P2 · Data foundation (5-6h).** 11 tables; generator in causal order:
  truth_sampler -> artifacts -> template chats -> noise -> labeler ->
  generate.py --n 200 --seed 42. Done: same seed => byte-identical DB.
- **P3 · L1 checklists (3-4h).** Weighted boolean checks per reason code,
  pure functions + pytest; retriever join fan-out; breakdown in case view.
  Done: pytest green; every case shows completeness.
- **P4 · L3 decision layer (3-4h).** Features [c, 0, auth_ok,
  log1p(prior_orders), rc_base_rate]; LogisticRegression on 140 train;
  EV gate + abstain band + floors + deadline lockout. Done: real calibrated
  verdicts end-to-end with ZERO LLM calls. Tag: llm-free milestone.
- **P5 · L2 caged LLM (4-5h).** llm.py wrapper (Gemini, disk cache, 429
  backoff, 5s sleeps); regenerate 200 transcripts on Flash-Lite; miner on
  Flash: JSON schema -> pydantic -> substring+timestamp verification;
  retrain L3; add --no-l2 ablation flag. Iterate prompts on 10 cases only.
  Done: 200 cached verified exhibit sets; --no-l2 runs.
- **P6 · Packet + dashboard (6-8h).** Jinja narrative per RC + verbatim
  verified exhibits (HTML print view); Streamlit final: queue w/ SLA
  colors, case view w/ glowing contradiction, metrics page, audit view.
  Done: both demo cases fully clickable.
- **P7 · Eval freeze (2h, sacred).** freeze.py commits split SHA-256;
  run_eval.py ONCE on 60 held-out: precision, recall, FP cost (Rs),
  net Rs vs accept-all & fight-all, --no-l2 ablation row. Numbers go
  verbatim into metrics page + deck slide 9 + README. Nothing tuned after.
- **P8 · Submission (4-5h).** README (couplet, architecture, 3-command
  quickstart, "zero API keys -- LLM outputs cached in-repo", metrics +
  ablation, limitations, privacy paragraph); run.sh < 2 min on clean
  clone; 3:00 video (kill -> restraint -> receipts), unlisted YouTube,
  link top of README; deck+PRD in /docs. Submit hours early.

Cut order if time collapses: PDF renderer, dashboard polish, calibration
plot, RC-DUP. NEVER: metrics page, frozen eval, ablation, video.
Standing rules: money in paise; every random call seeded; every LLM
response cached+committed; prompts iterated on 10-case subsample;
one commit per phase minimum.
