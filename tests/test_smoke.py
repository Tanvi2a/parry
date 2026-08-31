import datetime as dt
from schemas import Dispute
from engine.decide import decide


def test_decide_stub_returns_fight_with_ev():
    now = dt.datetime.now(dt.timezone.utc)
    d = Dispute(id="disp_000001", payment_id="pay_000001", amount=249900,
                reason_code="RC-FRAUD", respond_by=now, raised_at=now)
    r = decide(d)
    assert r["verdict"] == "FIGHT"
    assert r["ev_paise"] == int(0.75 * 249900) - 65000
