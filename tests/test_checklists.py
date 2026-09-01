import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from data.generator.generate import generate  # noqa: E402
from engine.checklists import completeness  # noqa: E402
from engine.retrieve import case_file  # noqa: E402


def _fabricated(rc="RC-INR", delivered=True, pod=True):
    return dict(
        dispute=dict(id="disp_x", reason_code=rc, amount=100000,
                     created_at=2_000_000),
        payment=dict(id="pay_x", amount=100000, captured_at=1_000_000),
        order=dict(id="ord_x", listing_match=1,
                   items=[{"name": "kurta", "qty": 1}]),
        customer=dict(prior_orders=3, device_ids=["dev_a"]),
        auth=dict(otp_result="passed", three_ds_result="passed",
                  device_known=1),
        shipment=dict(status="delivered" if delivered else "in_transit",
                      pod_url="pod/x.jpg" if pod else None,
                      address_match=1,
                      delivered_at=1_500_000 if delivered else None,
                      events=["picked_up", "delivered"] if delivered
                      else ["picked_up"]),
        chat=dict(return_offered=1, messages=[{"sender": "customer",
                                               "text": "hi", "ts": 1}]),
        siblings=[], refunds=[])


def test_known_scores_are_exact():
    c, bd = completeness(_fabricated())
    assert c == 1.0 and sum(b["weight"] for b in bd) == 1.0
    c2, _ = completeness(_fabricated(pod=False))
    assert c2 == 0.75            # loses pod (0.25)
    c3, _ = completeness(_fabricated(delivered=False, pod=False))
    assert c3 == 0.15            # only address_match survives


def test_every_generated_case_scores(tmp_path):
    generate(n=200, seed=42, db_path=tmp_path / "t.db")
    con = db.connect(tmp_path / "t.db")
    ids = [r[0] for r in con.execute("SELECT id FROM disputes")]
    assert len(ids) == 200
    for i in ids:
        cf = case_file(con, i)
        c, bd = completeness(cf)
        assert 0.0 <= c <= 1.0
        assert abs(sum(b["weight"] for b in bd) - 1.0) < 1e-9


def test_completeness_separates_winnable_on_train(tmp_path):
    generate(n=200, seed=42, db_path=tmp_path / "t.db")
    con = db.connect(tmp_path / "t.db")
    rows = con.execute("""SELECT dispute_id, winnable FROM ground_truth
                          WHERE split='train'""").fetchall()
    win, lose = [], []
    for i, w in rows:
        c, _ = completeness(case_file(con, i))
        (win if w == 1 else lose).append(c)
    assert sum(win) / len(win) > sum(lose) / len(lose) + 0.2
