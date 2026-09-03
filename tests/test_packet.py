import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
import engine.contradictions as l2  # noqa: E402
import packet.build as pb  # noqa: E402
from data.generator.generate import generate  # noqa: E402
from engine.llm import FakeProvider  # noqa: E402


def test_packet_renders_with_verified_quote(tmp_path, monkeypatch):
    generate(n=80, seed=42, db_path=tmp_path / "t.db")
    con = db.connect(tmp_path / "t.db")
    monkeypatch.setattr(l2, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(pb, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(pb, "OUT_DIR", tmp_path / "packets")
    row = con.execute("""SELECT d.id FROM disputes d
                         JOIN ground_truth g ON g.dispute_id = d.id
                         WHERE g.truth='friendly_fraud'
                           AND d.reason_code='RC-INR' LIMIT 1""").fetchone()
    cid = row[0]
    res, _ = l2.mine(con, cid, FakeProvider())
    path = pb.build(con, cid)
    html = path.read_text()
    assert "shipping_proof" in html and "customer_communication" in html
    if res["exhibits"]:
        assert res["exhibits"][0]["quote"] in html
