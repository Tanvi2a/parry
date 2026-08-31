import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from data.generator.generate import generate  # noqa: E402


def test_generator_is_deterministic_and_sane(tmp_path):
    s1 = generate(n=200, seed=42, db_path=tmp_path / "a.db")
    s2 = generate(n=200, seed=42, db_path=tmp_path / "b.db")
    # same seed => identical content, down to the hash
    assert s1["content_sha256"] == s2["content_sha256"]
    # different seed => different world
    s3 = generate(n=200, seed=7, db_path=tmp_path / "c.db")
    assert s3["content_sha256"] != s1["content_sha256"]
    # shape guarantees the rest of the build relies on
    assert s1["split"] == {"train": 140, "test": 60}
    assert s1["past_deadline"] == 1
    assert 2 <= s1["near_deadline"] <= 12
    assert 0.25 <= s1["truth_mix"]["friendly_fraud"] / 200 <= 0.45
    assert s1["flipped"] <= 25
    assert 40 <= s1["winnable"] <= 160
