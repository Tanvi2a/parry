"""Step 5: orchestrate truth -> artifacts -> chats -> noise -> labels ->
SQLite, with a stratified 140/60 split. One seed reproduces everything.

Usage:  python -m data.generator.generate --n 200 --seed 42
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import db  # noqa: E402
from data.generator import artifacts, chats, labeler, noise  # noqa: E402
from data.generator import truth_sampler as ts  # noqa: E402

DEFAULT_ANCHOR = "2026-09-03T12:00:00+05:30"   # demo day, noon IST


def _epoch(iso):
    return int(dt.datetime.fromisoformat(iso).timestamp())


def generate(n=200, seed=42, db_path=None, anchor_iso=DEFAULT_ANCHOR,
             test_size=60):
    rng = random.Random(seed)
    anchor = _epoch(anchor_iso)

    # ---- build all cases in memory, in causal order ----
    cases = []
    for i in range(n):
        truth = ts.sample_truth(rng)
        rc = ts.sample_reason_code(rng, truth)
        c = artifacts.build_case(rng, i, truth, rc, anchor)
        c = chats.build_chat(rng, c, anchor)
        cases.append(c)
    cases = noise.apply(rng, cases, anchor)
    for c in cases:
        labeler.label(rng, c)

    # ---- stratified split by reason code: exactly `test_size` held-out ----
    by_rc = collections.defaultdict(list)
    for c in cases:
        by_rc[c["rc"]].append(c["i"])
    test_ids = set()
    for rc in sorted(by_rc):
        ids = by_rc[rc][:]
        rng.shuffle(ids)
        k = round(len(ids) * test_size / n)
        test_ids.update(ids[:k])
    pool = [c["i"] for c in cases if c["i"] not in test_ids]
    rng.shuffle(pool)
    while len(test_ids) < test_size:
        test_ids.add(pool.pop())
    while len(test_ids) > test_size:
        test_ids.remove(sorted(test_ids)[-1])
    for c in cases:
        c["split"] = "test" if c["i"] in test_ids else "train"

    # ---- write SQLite (fresh file each run => reproducible) ----
    path = pathlib.Path(db_path) if db_path else db.DB
    for p in (path, path.with_suffix(".db-wal"), path.with_suffix(".db-shm")):
        p.unlink(missing_ok=True)
    con = db.connect(path)
    for c in cases:
        con.execute("INSERT INTO customers VALUES(?,?,?,?)",
                    tuple(c["customer"].values()))
        con.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)",
                    tuple(c["order"].values()))
        if "order2" in c:
            con.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)",
                        tuple(c["order2"].values()))
        for p in c["payments"]:
            con.execute("INSERT INTO payments VALUES(?,?,?,?,?,?)",
                        tuple(p.values()))
        con.execute("INSERT INTO auth_log VALUES(?,?,?,?,?,?)",
                    tuple(c["auth"].values()))
        con.execute("INSERT INTO shipments VALUES(?,?,?,?,?,?,?,?)",
                    tuple(c["shipment"].values()))
        con.execute("INSERT INTO chat_threads VALUES(?,?,?,?,?,?,?)",
                    tuple(c["chat"].values()))
        for r in c["refunds"]:
            con.execute("INSERT INTO refunds VALUES(?,?,?,?,?)",
                        tuple(r.values()))
        con.execute("INSERT INTO disputes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(c["dispute"].values()))
        con.execute("INSERT INTO ground_truth VALUES(?,?,?,?,?)",
                    (c["dispute"]["id"], c["truth"], c["winnable"],
                     c["flipped"], c["split"]))
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()

    # ---- summary + canonical content hash (determinism proof) ----
    rows = []
    con = db.connect(path)
    for t in ("customers", "orders", "payments", "auth_log", "shipments",
              "chat_threads", "refunds", "disputes", "ground_truth"):
        rows += [t] + [str(r) for r in
                       con.execute(f"SELECT * FROM {t} ORDER BY 1")]
    con.close()
    content_hash = hashlib.sha256("\n".join(rows).encode()).hexdigest()

    truth_counts = collections.Counter(c["truth"] for c in cases)
    rc_counts = collections.Counter(c["rc"] for c in cases)
    summary = dict(
        n=n, seed=seed, anchor=anchor_iso,
        truth_mix=dict(sorted(truth_counts.items())),
        reason_codes=dict(sorted(rc_counts.items())),
        winnable=sum(c["winnable"] for c in cases),
        flipped=sum(c["flipped"] for c in cases),
        pod_lost_to_noise=sum(1 for c in cases if c.get("noise_pod_lost")),
        near_deadline=sum(1 for c in cases
                          if 0 < c["dispute"]["respond_by"] - anchor
                          <= 36 * 3600),
        past_deadline=sum(1 for c in cases
                          if c["dispute"]["respond_by"] < anchor),
        split=dict(train=sum(1 for c in cases if c["split"] == "train"),
                   test=sum(1 for c in cases if c["split"] == "test")),
        avg_amount_rs=round(sum(c["dispute"]["amount"]
                                for c in cases) / n / 100),
        content_sha256=content_hash,
    )
    meta_path = path.parent / "dataset_meta.json"
    meta_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--anchor", default=DEFAULT_ANCHOR)
    args = ap.parse_args()
    s = generate(n=args.n, seed=args.seed, anchor_iso=args.anchor)
    print(json.dumps(s, indent=2, sort_keys=True))
