"""Mine every seeded dispute through L2, cache-first.
  python -m engine.run_l2 --limit 10     iterate the prompt on a subsample
  python -m engine.run_l2                the full pass (uncached calls
                                          sleep between them; a full fresh
                                          run is ~20 min on the free tier)
"""
import argparse
import collections
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from engine.contradictions import mine  # noqa: E402
from engine.llm import LLMError, get_provider  # noqa: E402


def run(limit=None, force=False):
    con = db.connect()
    provider, cfg = get_provider()
    ids = [r[0] for r in con.execute("SELECT id FROM disputes ORDER BY id")]
    if limit:
        ids = ids[:limit]
    hits = mined = dropped = found = 0
    skipped = []
    per_rc = collections.defaultdict(list)
    for k, i in enumerate(ids, 1):
        try:
            res, from_cache = mine(con, i, provider, force=force)
        except LLMError as e:
            if "DAILY" in str(e):
                print(f"\nSTOP: {e}")
                print(f"progress is cached -- fix the model/quota and "
                      f"re-run; completed cases will be skipped.")
                break
            print(f"[{k}/{len(ids)}] {i} FAILED once ({e}); "
                  f"waiting 60s and retrying...")
            time.sleep(60)
            try:
                res, from_cache = mine(con, i, provider, force=force)
            except LLMError as e2:
                print(f"[{k}/{len(ids)}] {i} skipped: {e2}")
                skipped.append(i)
                continue
        hits += from_cache
        mined += (not from_cache)
        dropped += len(res["dropped"])
        found += res["contradiction_count"]
        rc = con.execute("SELECT reason_code FROM disputes WHERE id=?",
                         (i,)).fetchone()[0]
        per_rc[rc].append(res["contradiction_count"])
        if not from_cache:
            print(f"[{k}/{len(ids)}] {i} mined -> "
                  f"{res['contradiction_count']} verified")
            time.sleep(cfg["sleep_s"])
    print(f"\ndone: {len(ids)} cases · {mined} mined live · {hits} from "
          f"cache · {found} verified exhibits · {dropped} dropped by "
          f"the verifier")
    if skipped:
        print(f"skipped ({len(skipped)}) -- re-run to retry: {skipped}")
    for rc in sorted(per_rc):
        v = per_rc[rc]
        print(f"  {rc:<9} mean verified contradictions = "
              f"{sum(v) / len(v):.2f}")
    # train-split-only: contradictions by hidden truth (sanity, not eval)
    rows = con.execute("""SELECT g.dispute_id, g.truth FROM ground_truth g
                          WHERE g.split='train'""").fetchall()
    by_truth = collections.defaultdict(list)
    from engine.contradictions import cached_count
    for did, truth in rows:
        by_truth[truth].append(cached_count(did))
    print("signal check (train split only):")
    for t in sorted(by_truth):
        v = by_truth[t]
        print(f"  {t:<17} mean = {sum(v) / len(v):.2f}  (n={len(v)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(limit=args.limit, force=args.force)