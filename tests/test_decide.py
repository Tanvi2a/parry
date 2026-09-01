import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
import engine.decide as decide_mod  # noqa: E402
from data.generator.generate import generate  # noqa: E402
from engine.model import train  # noqa: E402

ANCHOR = 1756883700  # not used; real anchor read from summary below


def _setup(tmp_path):
    s = generate(n=200, seed=42, db_path=tmp_path / "t.db")
    import datetime as dt
    now = int(dt.datetime.fromisoformat(s["anchor"]).timestamp())
    train(db_path=tmp_path / "t.db", out_path=tmp_path / "m.joblib")
    decide_mod.MODEL_PATH = tmp_path / "m.joblib"
    decide_mod.reset_cache()
    return db.connect(tmp_path / "t.db"), now


def test_gates_hold_on_every_case(tmp_path):
    con, now = _setup(tmp_path)
    ids = [r[0] for r in con.execute("SELECT id FROM disputes ORDER BY id")]
    expired = 0
    for i in ids:
        dec = decide_mod.decide(con, i, now=now)
        assert dec["verdict"] in ("FIGHT", "ACCEPT", "ABSTAIN", "EXPIRED")
        if dec["verdict"] == "EXPIRED":
            expired += 1
        if dec["verdict"] in ("FIGHT", "ACCEPT"):
            assert not (0.45 <= dec["p_win"] <= 0.60)
        if dec["verdict"] == "FIGHT":
            assert dec["p_win"] * dec_amount(con, i) > 65000
            if dec["mode"] == "auto":
                assert dec["p_win"] >= 0.75
                assert dec_amount(con, i) <= 500000
                assert dec["completeness"] >= 0.8
    assert expired == 1


def dec_amount(con, dispute_id):
    return con.execute("SELECT amount FROM disputes WHERE id=?",
                       (dispute_id,)).fetchone()[0]


def test_decisions_are_deterministic(tmp_path):
    con, now = _setup(tmp_path)
    ids = [r[0] for r in con.execute("SELECT id FROM disputes ORDER BY id")]
    a = [decide_mod.decide(con, i, now=now)["verdict"] for i in ids]
    b = [decide_mod.decide(con, i, now=now)["verdict"] for i in ids]
    assert a == b


def test_model_bundle_shape(tmp_path):
    s = generate(n=200, seed=42, db_path=tmp_path / "t2.db")
    rep = train(db_path=tmp_path / "t2.db", out_path=tmp_path / "m2.joblib")
    assert rep["n_train"] == 140
    assert len(rep["coefficients"]) == 5
    assert rep["cv_accuracy_at_0p5"] > 0.8
