"""Inspect L1 by eye.
  python -m engine.l1_report              -> dataset-level completeness stats
  python -m engine.l1_report disp_0015    -> one case, full breakdown
Label-joined stats use the TRAIN split only -- the held-out 60 stay unseen."""
import collections
import sys

import db
from engine.checklists import completeness
from engine.retrieve import case_file


def one(con, dispute_id):
    cf = case_file(con, dispute_id)
    if cf is None:
        print(f"no such dispute: {dispute_id}")
        return
    d, score, breakdown = cf["dispute"], *completeness(cf)
    print(f"\n{d['id']}  ·  {d['reason_code']}  ·  Rs {d['amount']/100:,.0f}")
    print(f"completeness c = {score}")
    for b in breakdown:
        mark = "PASS" if b["passed"] else "----"
        print(f"  [{mark}] {b['check']:<28} weight {b['weight']:.2f}")
    print("\ncase file glance:")
    print(f"  auth: otp={cf['auth']['otp_result']} "
          f"device_known={cf['auth']['device_known']} "
          f"prior_orders={cf['customer']['prior_orders']}")
    if cf["shipment"]:
        s = cf["shipment"]
        print(f"  shipment: {s['status']} pod={'yes' if s['pod_url'] else 'NO'}"
              f" events={s['events']}")
    if cf["chat"]:
        for m in cf["chat"]["messages"]:
            print(f"  chat[{m['sender']}]: {m['text']}")


def report(con):
    ids = [r[0] for r in con.execute("SELECT id FROM disputes ORDER BY id")]
    by_rc = collections.defaultdict(list)
    scores = {}
    for i in ids:
        cf = case_file(con, i)
        c, _ = completeness(cf)
        scores[i] = c
        by_rc[cf["dispute"]["reason_code"]].append(c)
    print(f"cases scored: {len(ids)}")
    for rc in sorted(by_rc):
        v = by_rc[rc]
        print(f"  {rc:<9} n={len(v):<4} mean c = {sum(v)/len(v):.3f}")
    rows = con.execute("""SELECT dispute_id, winnable FROM ground_truth
                          WHERE split='train'""").fetchall()
    win = [scores[i] for i, w in rows if w == 1]
    lose = [scores[i] for i, w in rows if w == 0]
    print("signal check (train split only):")
    print(f"  winnable   mean c = {sum(win)/len(win):.3f}  (n={len(win)})")
    print(f"  unwinnable mean c = {sum(lose)/len(lose):.3f}  (n={len(lose)})")


if __name__ == "__main__":
    con = db.connect()
    if len(sys.argv) > 1:
        one(con, sys.argv[1])
    else:
        report(con)
