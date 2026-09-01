"""Phase 1's stub test, grown up: the walking skeleton's decide() is now
the real engine. A dispute with no linked records must ABSTAIN to a human
-- the graceful path for live webhooks referencing unknown payments."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from engine.decide import decide  # noqa: E402


def test_unknown_payment_abstains_to_human(tmp_path):
    con = db.connect(tmp_path / "s.db")
    now = int(time.time())
    con.execute("INSERT INTO disputes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("disp_orphan", "dispute", "pay_nowhere", 249900, "INR", 0,
                 "RC-FRAUD", "x", now + 7 * 86400, "open", "chargeback", now))
    con.commit()
    dec = decide(con, "disp_orphan", now=now)
    assert dec["verdict"] == "ABSTAIN"
    assert dec["mode"] == "review"
    assert "linked records" in dec["rationale"]
