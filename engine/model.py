"""L3 training: a five-feature logistic regression on the 140 train cases.
Calibration is CHECKED via 5-fold cross-validated reliability buckets --
no fine-tuning, no tree ensembles, coefficients small enough to print.

  python -m engine.model        trains, prints, saves data/out/model.joblib
"""
import json
import pathlib
import sys

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from engine.checklists import completeness  # noqa: E402
from engine.contradictions import cached_count  # noqa: E402
from engine.features import FEATURES, extract  # noqa: E402
from engine.retrieve import case_file  # noqa: E402

MODEL_PATH = pathlib.Path("data/out/model.joblib")
MODEL_PATH_NO_L2 = pathlib.Path("data/out/model_no_l2.joblib")


def train(db_path=None, out_path=MODEL_PATH):
    con = db.connect(db_path)
    rows = con.execute("""SELECT g.dispute_id, g.winnable, d.reason_code
                          FROM ground_truth g JOIN disputes d
                            ON d.id = g.dispute_id
                          WHERE g.split='train'""").fetchall()
    # reason-code base win rates, train only, frozen into the bundle
    rc_base = {}
    for _, w, rc in rows:
        rc_base.setdefault(rc, []).append(w)
    rc_base_rates = {rc: round(sum(v) / len(v), 4)
                     for rc, v in rc_base.items()}
    rc_base_rates["__overall__"] = round(
        sum(w for _, w, _ in rows) / len(rows), 4)

    X, X0, y = [], [], []
    for did, w, _ in rows:
        cf = case_file(con, did)
        c, _bd = completeness(cf)
        X.append(extract(cf, c, rc_base_rates,
                         contradiction_count=cached_count(did)))
        X0.append(extract(cf, c, rc_base_rates, contradiction_count=0))
        y.append(w)
    X, X0, y = np.array(X), np.array(X0), np.array(y)

    # calibration check: 5-fold cross-validated probabilities
    cv_p = cross_val_predict(LogisticRegression(max_iter=1000), X, y,
                             cv=5, method="predict_proba")[:, 1]
    buckets = []
    for lo, hi in [(0, .25), (.25, .5), (.5, .75), (.75, 1.001)]:
        m = (cv_p >= lo) & (cv_p < hi)
        if m.sum():
            buckets.append(dict(bucket=f"{lo:.2f}-{min(hi, 1):.2f}",
                                n=int(m.sum()),
                                predicted=round(float(cv_p[m].mean()), 3),
                                actual=round(float(y[m].mean()), 3)))
    acc = float(((cv_p >= 0.5).astype(int) == y).mean())

    final = LogisticRegression(max_iter=1000).fit(X, y)
    final0 = LogisticRegression(max_iter=1000).fit(X0, y)
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(model=final, rc_base_rates=rc_base_rates,
                     features=FEATURES, n_train=len(y)), out_path)
    joblib.dump(dict(model=final0, rc_base_rates=rc_base_rates,
                     features=FEATURES, n_train=len(y)),
                pathlib.Path(out_path).parent / MODEL_PATH_NO_L2.name)

    report_path = pathlib.Path(out_path).parent / "model_report.json"
    report = dict(
        n_train=len(y), features=FEATURES,
        coefficients={f: round(float(c), 3)
                      for f, c in zip(FEATURES, final.coef_[0])},
        intercept=round(float(final.intercept_[0]), 3),
        rc_base_rates=rc_base_rates,
        cv_accuracy_at_0p5=round(acc, 3),
        ablation_no_l2_coefficients={
            f: round(float(c), 3)
            for f, c in zip(FEATURES, final0.coef_[0])},
        calibration_buckets=buckets,
        saved_to=str(out_path),
    )
    report_path.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
