"""The Evidence Retriever: deterministic SQL joins, nothing else.
Given a dispute id, assemble the complete case file from the merchant's
own tables. Tolerant of missing links (a live webhook may reference a
payment we have no records for -- downstream, that means ABSTAIN).
No LLM, no scoring, no ground_truth."""
import json
import sqlite3


def _row(r):
    return dict(r) if r is not None else None


def case_file(con, dispute_id):
    con.row_factory = sqlite3.Row
    d = con.execute("SELECT * FROM disputes WHERE id=?",
                    (dispute_id,)).fetchone()
    if d is None:
        return None
    p = con.execute("SELECT * FROM payments WHERE id=?",
                    (d["payment_id"],)).fetchone()
    o = (con.execute("SELECT * FROM orders WHERE id=?",
                     (p["order_id"],)).fetchone() if p else None)
    cu = (con.execute("SELECT * FROM customers WHERE id=?",
                      (o["customer_id"],)).fetchone() if o else None)
    a = (con.execute("SELECT * FROM auth_log WHERE payment_id=?",
                     (p["id"],)).fetchone() if p else None)
    s = (con.execute("SELECT * FROM shipments WHERE order_id=?",
                     (o["id"],)).fetchone() if o else None)
    ch = (con.execute("SELECT * FROM chat_threads WHERE order_id=?",
                      (o["id"],)).fetchone() if o else None)
    siblings = (con.execute(
        """SELECT p2.*, o2.items AS sib_items FROM payments p2
           JOIN orders o2 ON o2.id = p2.order_id
           WHERE o2.customer_id = ? AND p2.id != ?
             AND ABS(p2.captured_at - ?) < 2 * 86400""",
        (cu["id"], p["id"], p["captured_at"])).fetchall()
        if (cu and p) else [])
    pay_ids = ([p["id"]] if p else []) + [r["id"] for r in siblings]
    refunds = (con.execute(
        f"""SELECT * FROM refunds
            WHERE payment_id IN ({','.join('?' * len(pay_ids))})""",
        pay_ids).fetchall() if pay_ids else [])

    cf = dict(dispute=_row(d), payment=_row(p), order=_row(o),
              customer=_row(cu), auth=_row(a), shipment=_row(s),
              chat=_row(ch), siblings=[_row(r) for r in siblings],
              refunds=[_row(r) for r in refunds])
    # parse JSON columns once, here, so downstream code never touches json
    if cf["order"]:
        cf["order"]["items"] = json.loads(cf["order"]["items"])
    if cf["customer"]:
        cf["customer"]["device_ids"] = json.loads(
            cf["customer"]["device_ids"])
    if cf["shipment"]:
        cf["shipment"]["events"] = json.loads(cf["shipment"]["events"])
    if cf["chat"]:
        cf["chat"]["messages"] = json.loads(cf["chat"]["messages"])
    for sib in cf["siblings"]:
        sib["sib_items"] = json.loads(sib["sib_items"])
    return cf
