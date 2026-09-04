"""Phase 7 -- the sacred hour. Freezes the split manifest (SHA-256 over the
held-out ids) and runs the evaluation ONCE on the 60 test cases:
precision & recall of FIGHT, false-positive cost in Rs, net Rs against
accept-all and fight-all baselines, and the --no-l2 ablation row.
Writes data/out/eval.json (the Metrics page renders it) and
data/out/split_manifest.json.

  python -m engine.run_eval

Policy note baked into the numbers: ABSTAIN and EXPIRED cases are routed
to humans and are NOT counted as fights; they are reported separately.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from engine import config  # noqa: E402
from engine.decide import decide  # noqa: E402

OUT = pathlib.Path("data/out")


def _freeze(con):
    rows = con.execute("""SELECT dispute_id FROM ground_truth
                          WHERE split='test' ORDER BY dispute_id""").fetchall()
    test_ids = [r[0] for r in rows]
    sha = hashlib.sha256("\n".join(test_ids).encode()).hexdigest()
    manifest_path = OUT / "split_manifest.json"
    if manifest_path.exists():
        prev = json.loads(manifest_path.read_text())
        if prev["sha256"] != sha:
            raise SystemExit("SPLIT CHANGED since freeze -- refusing to "
                             "eval. Regenerate with the frozen seed.")
        print(f"split manifest verified: sha256={sha[:16]}... (frozen "
              f"{prev['frozen_at']})")
    else:
        manifest_path.write_text(json.dumps(dict(
            sha256=sha, n_test=len(test_ids), test_ids=test_ids,
            frozen_at=dt.datetime.now().isoformat(timespec="seconds")),
            indent=2))
        print(f"split FROZEN: {len(test_ids)} held-out cases, "
              f"sha256={sha[:16]}...")
    return test_ids, sha


def _pass(con, test_rows, now, cost):
    tp = fp = fought = abstained = expired = auto = 0
    net = 0
    for did, winnable, amount in test_rows:
        dec = decide(con, did, now=now)
        v = dec["verdict"]
        if v == "FIGHT":
            fought += 1
            auto += (dec["mode"] == "auto")
            if winnable:
                tp += 1
                net += amount - cost
            else:
                fp += 1
                net -= cost
        elif v == "ABSTAIN":
            abstained += 1
        elif v == "EXPIRED":
            expired += 1
    total_winnable = sum(w for _, w, _ in test_rows)
    precision = round(tp / fought, 4) if fought else None
    recall = round(tp / total_winnable, 4) if total_winnable else None
    return dict(fought=fought, auto_submitted=auto, abstained=abstained,
                expired=expired, true_positives=tp, false_positives=fp,
                precision=precision, recall=recall,
                fp_cost_rs=round(fp * cost / 100),
                net_rs=round(net / 100))


def run():
    con = db.connect()
    cfg = config.load()
    cost = cfg["cost_to_fight_paise"]
    meta = json.loads((OUT / "dataset_meta.json").read_text())
    now = int(dt.datetime.fromisoformat(meta["anchor"]).timestamp())
    test_ids, sha = _freeze(con)
    q = ",".join("?" * len(test_ids))
    test_rows = con.execute(
        f"""SELECT g.dispute_id, g.winnable, d.amount
            FROM ground_truth g JOIN disputes d ON d.id = g.dispute_id
            WHERE g.dispute_id IN ({q}) ORDER BY g.dispute_id""",
        test_ids).fetchall()

    os.environ.pop("PARRY_NO_L2", None)
    live = _pass(con, test_rows, now, cost)
    os.environ["PARRY_NO_L2"] = "1"
    ablation = _pass(con, test_rows, now, cost)
    os.environ.pop("PARRY_NO_L2", None)

    fight_all = sum((a - cost) if w else -cost for _, w, a in test_rows)
    result = dict(
        n_test=len(test_rows),
        total_winnable=sum(w for _, w, _ in test_rows),
        split_sha256=sha,
        evaluated_at=dt.datetime.now().isoformat(timespec="seconds"),
        policy_note=("ABSTAIN and EXPIRED route to humans and are not "
                     "counted as fights; reported separately."),
        cost_to_fight_rs=cost // 100,
        parry=live,
        parry_no_l2_ablation=ablation,
        baselines=dict(accept_all_net_rs=0,
                       fight_all_net_rs=round(fight_all / 100)),
    )
    (OUT / "eval.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print("\nwritten: data/out/eval.json (Metrics page now renders it)")


if __name__ == "__main__":
    run()
