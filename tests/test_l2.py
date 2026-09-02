import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
import engine.contradictions as l2  # noqa: E402
from data.generator.generate import generate  # noqa: E402
from engine.contradictions import cached_count, mine, verify  # noqa: E402
from engine.llm import FakeProvider  # noqa: E402

MSGS = [{"sender": "customer", "ts": 100,
         "text": "bhai order aa gaya but size chhota hai"},
        {"sender": "support", "ts": 200, "text": "we can offer an exchange"}]


def test_verifier_is_the_cage():
    good = dict(quote="order aa gaya", source="customer", ts=100,
                type="possession_admission", explanation="")
    hallucinated = dict(quote="I received the parcel yesterday",
                        source="customer", ts=100, type="other",
                        explanation="")
    wrong_ts = dict(quote="order aa gaya", source="customer", ts=999,
                    type="other", explanation="")
    wrong_src = dict(quote="order aa gaya", source="support", ts=100,
                     type="other", explanation="")
    bad_schema = dict(quote="order aa gaya", source="customer")
    kept, dropped = verify(
        [good, hallucinated, wrong_ts, wrong_src, bad_schema], MSGS)
    assert len(kept) == 1 and kept[0]["quote"] == "order aa gaya"
    assert len(dropped) == 4


def test_mine_caches_and_replays(tmp_path, monkeypatch):
    generate(n=60, seed=42, db_path=tmp_path / "t.db")
    con = db.connect(tmp_path / "t.db")
    monkeypatch.setattr(l2, "CACHE_DIR", tmp_path / "cache")
    provider = FakeProvider()
    ids = [r[0] for r in
           con.execute("SELECT id FROM disputes ORDER BY id LIMIT 30")]
    for i in ids:
        mine(con, i, provider)
    first_calls = provider.calls
    assert first_calls == 30
    for i in ids:
        res, from_cache = mine(con, i, provider)
        assert from_cache
    assert provider.calls == first_calls          # zero new calls
    counts = [cached_count(i) for i in ids]
    assert sum(counts) > 0                        # fake finds the plants
    monkeypatch.setenv("PARRY_NO_L2", "1")
    assert all(cached_count(i) == 0 for i in ids)  # ablation mutes it


def test_cache_file_is_inspectable(tmp_path, monkeypatch):
    generate(n=20, seed=42, db_path=tmp_path / "t.db")
    con = db.connect(tmp_path / "t.db")
    monkeypatch.setattr(l2, "CACHE_DIR", tmp_path / "cache")
    res, _ = mine(con, "disp_0000", FakeProvider())
    on_disk = json.loads((tmp_path / "cache" / "disp_0000.json").read_text())
    assert on_disk["prompt_version"] == "v1"
    assert "raw" in on_disk and "exhibits" in on_disk
