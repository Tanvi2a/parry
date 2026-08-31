import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from schemas import Dispute  # noqa: E402
from engine.decide import decide  # noqa: E402


def test_decide_stub_returns_fight_with_ev():
    now = int(time.time())
    d = Dispute(id="disp_000001", payment_id="pay_000001", amount=249900,
                reason_code="RC-FRAUD", respond_by=now + 7 * 86400,
                created_at=now)
    r = decide(d)
    assert r["verdict"] == "FIGHT"
    assert r["ev_paise"] == int(0.75 * 249900) - 65000
