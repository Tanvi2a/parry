"""L3 in production: calibrated p(win) -> the gate stack. The LLM never
appears here; contradiction_count arrives as a number (0 until Phase 5).

Gate order, checked top to bottom:
  1. missing linked records        -> ABSTAIN / review
  2. past respond_by               -> EXPIRED / review (never submit)
  3. p inside abstain band         -> ABSTAIN / review
  4. p x amount > cost_to_fight    -> FIGHT (auto only if all floors met)
  5. otherwise                     -> ACCEPT + sub-recommendation
"""
import json
import os
import pathlib
import time

import joblib

from engine import config
from engine.checklists import completeness
from engine.contradictions import cached_count
from engine.features import FEATURES, extract
from engine.retrieve import case_file

MODEL_PATH = pathlib.Path("data/out/model.joblib")
MODEL_PATH_NO_L2 = pathlib.Path("data/out/model_no_l2.joblib")
_bundles = {}


def _no_l2():
    return os.environ.get("PARRY_NO_L2") == "1"


def reset_cache():
    _bundles.clear()


def _model_path():
    return MODEL_PATH_NO_L2 if _no_l2() else MODEL_PATH


def _load():
    key = str(_model_path())
    if key not in _bundles:
        _bundles[key] = joblib.load(_model_path())
    return _bundles[key]


def decide(con, dispute_id, now=None, contradiction_count=None):
    cfg = config.load()
    now = int(now if now is not None else time.time())
    cf = case_file(con, dispute_id)
    if cf is None:
        return None
    d = cf["dispute"]
    A, C = d["amount"], cfg["cost_to_fight_paise"]

    if contradiction_count is None:
        contradiction_count = cached_count(dispute_id)
    core_missing = any(cf[k] is None
                       for k in ("payment", "order", "customer", "auth"))
    if core_missing or not _model_path().exists():
        why = ("linked records not found -- route to human"
               if core_missing else "model not trained -- route to human")
        dec = dict(verdict="ABSTAIN", p_win=None, ev_paise=None,
                   mode="review", rationale=why, completeness=None,
                   features=None)
    else:
        c, breakdown = completeness(cf)
        b = _load()
        x = extract(cf, c, b["rc_base_rates"], contradiction_count)
        p = float(b["model"].predict_proba([x])[0][1])
        ev = int(p * A) - C
        lo, hi = cfg["abstain_band"]
        if d["respond_by"] < now:
            verdict, mode = "EXPIRED", "review"
            why = "past respond_by -- flagged, never submitted"
        elif lo <= p <= hi:
            verdict, mode = "ABSTAIN", "review"
            why = f"p(win)={p:.2f} inside abstain band [{lo:.2f},{hi:.2f}]"
        elif p * A > C:
            verdict = "FIGHT"
            auto = (p >= cfg["p_win_floor"]
                    and A <= cfg["auto_submit_cap_paise"]
                    and c >= cfg["completeness_floor"])
            mode = "auto" if auto else "review"
            why = (f"EV +Rs {ev / 100:,.0f}: p={p:.2f} x Rs {A / 100:,.0f} "
                   f"> Rs {C / 100:,.0f} cost to fight")
        else:
            verdict, mode = "ACCEPT", "review"
            why = f"EV Rs {ev / 100:,.0f}: not worth fighting"
            if d["reason_code"] == "RC-DUP":
                why += (" -- refund already processed, attach proof"
                        if cf["refunds"] else
                        " -- true duplicate, issue refund")
        dec = dict(verdict=verdict, p_win=round(p, 4), ev_paise=ev,
                   mode=mode, rationale=why, completeness=c,
                   features=dict(zip(FEATURES, [round(v, 4) for v in x])))

    blob = json.dumps(dict(x=dec["features"], rationale=dec["rationale"],
                           completeness=dec["completeness"]))
    con.execute("INSERT OR REPLACE INTO decisions VALUES(?,?,?,?,?,?,?)",
                (dispute_id, dec["verdict"], dec["p_win"], dec["ev_paise"],
                 dec["mode"], blob, now))
    con.commit()
    return dec
