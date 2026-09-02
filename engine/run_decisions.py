"""Decide every seeded dispute.  --no-l2 mutes the contradiction feature
(the ablation row for the eval). (now = the dataset anchor, so the one
past-deadline case is EXPIRED on any machine, any day).

  python -m engine.run_decisions
"""
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from api.audit import log  # noqa: E402
from engine.decide import decide  # noqa: E402


def run(db_path=None):
    con = db.connect(db_path)
    meta_path = (pathlib.Path(db_path).parent if db_path
                 else pathlib.Path("data/out")) / "dataset_meta.json"
    meta = json.loads(meta_path.read_text())
    import datetime as dt
    now = int(dt.datetime.fromisoformat(meta["anchor"]).timestamp())

    ids = [r[0] for r in con.execute("SELECT id FROM disputes ORDER BY id")]
    counts = collections.Counter()
    p_by_verdict = collections.defaultdict(list)
    examples = collections.defaultdict(list)
    for i in ids:
        dec = decide(con, i, now=now)
        log(con, "parry", f"decision:{i}:{dec['verdict']}:{dec['mode']}")
        counts[(dec["verdict"], dec["mode"])] += 1
        if dec["p_win"] is not None:
            p_by_verdict[dec["verdict"]].append(dec["p_win"])
        if len(examples[dec["verdict"]]) < 3:
            examples[dec["verdict"]].append(i)
    print(f"decided: {len(ids)}")
    for (v, m), n in sorted(counts.items()):
        print(f"  {v:<8} {m:<7} n={n}")
    for v, ps in sorted(p_by_verdict.items()):
        print(f"  mean p(win) | {v:<8} = {sum(ps) / len(ps):.3f}")
    print("demo shopping list:", dict(examples))
    return counts


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-l2", action="store_true")
    args = ap.parse_args()
    if args.no_l2:
        os.environ["PARRY_NO_L2"] = "1"
        print("mode: ABLATION (contradiction feature muted)")
    run()
