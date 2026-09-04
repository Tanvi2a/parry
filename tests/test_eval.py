import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def test_eval_output_shape():
    # runs against the repo's own artifacts if present; hermetic checks only
    p = pathlib.Path("data/out/eval.json")
    if not p.exists():
        return  # eval not run yet on this machine -- nothing to assert
    ev = json.loads(p.read_text())
    assert ev["n_test"] == 60
    for block in (ev["parry"], ev["parry_no_l2_ablation"]):
        assert 0 <= (block["precision"] or 0) <= 1
        assert 0 <= (block["recall"] or 0) <= 1
        assert block["fought"] + block["abstained"] + block["expired"] <= 60
    assert ev["baselines"]["accept_all_net_rs"] == 0
