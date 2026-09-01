"""The Evidence Retriever: deterministic SQL joins, nothing else.
Given a dispute id, assemble the complete case file from the merchant's
own tables. No LLM, no scoring, no ground_truth -- this module may only
read what a real merchant's systems would hold."""
import json
import sqlite3


def case_file(con, dispute_id):
    con.row_factory = sqlite3.Row
    d = con.execute("SELECT * FROM disputes WHERE id=?",
                    (dispute_id,)).fetchone()
    if d is None:
        return None
    p = con.execute("SELECT * FROM payments WHERE id=?",
                    (d["payment_id"],)).fetchone()
    o = con.execute("SELECT * FROM orders WHERE id=?",
                    (p["order_id"],)).fetchone()
    cu = con.execute("SELECT * FROM customers WHERE id=?",
                     (o["customer_id"],)).fetchone()
    a = con.execute("SELECT * FROM auth_log WHERE payment_id=?",
                    (p["id"],)).fetchone()
    s = con.execute("SELECT * FROM shipments WHERE order_id=?",
                    (o["id"],)).fetchone()
    ch = con.execute("SELECT * FROM chat_threads WHERE order_id=?",
                     (o["id"],)).fetchone()
    siblings = con.execute(
        """SELECT p2.*, o2.items AS sib_items FROM payments p2
           JOIN orders o2 ON o2.id = p2.order_id
           WHERE o2.customer_id = ? AND p2.id != ?
             AND ABS(p2.captured_at - ?) < 2 * 86400""",
        (cu["id"], p["id"], p["captured_at"])).fetchall()
    pay_ids = [p["id"]] + [r["id"] for r in siblings]
    refunds = con.execute(
        f"""SELECT * FROM refunds
            WHERE payment_id IN ({','.join('?' * len(pay_ids))})""",
        pay_ids).fetchall()

    def row(r):
        return dict(r) if r is not None else None

    cf = dict(dispute=row(d), payment=row(p), order=row(o),
              customer=row(cu), auth=row(a), shipment=row(s),
              chat=row(ch), siblings=[row(r) for r in siblings],
              refunds=[row(r) for r in refunds])
    # parse JSON columns once, here, so downstream code never touches json
    cf["order"]["items"] = json.loads(cf["order"]["items"])
    cf["customer"]["device_ids"] = json.loads(cf["customer"]["device_ids"])
    if cf["shipment"]:
        cf["shipment"]["events"] = json.loads(cf["shipment"]["events"])
    if cf["chat"]:
        cf["chat"]["messages"] = json.loads(cf["chat"]["messages"])
    for sib in cf["siblings"]:
        sib["sib_items"] = json.loads(sib["sib_items"])
    return cf
