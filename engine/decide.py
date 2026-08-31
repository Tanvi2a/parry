"""Phase 1 stub: a three-line lie. The pipe exists first; truth flows
through it in Phases 3-5 (checklists -> logistic model -> EV gate)."""
COST_TO_FIGHT = 65000  # paise = Rs 650, parametrized properly in Phase 4


def decide(d):
    p = 0.75  # hardcoded -- replaced by the real engine
    return {"verdict": "FIGHT", "p_win": p,
            "ev_paise": int(p * d.amount) - COST_TO_FIGHT}
