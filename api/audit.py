"""Append-only, hash-chained audit log. Each row fingerprints itself AND
the previous row, so any edit to history breaks the chain visibly."""
import hashlib
import json
from datetime import datetime, timezone


def log(con, actor, action):
    row = con.execute("SELECT payload_hash FROM audit_events "
                      "ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row[0] if row else "genesis"
    ts = datetime.now(timezone.utc).isoformat()
    h = hashlib.sha256(json.dumps(
        {"ts": ts, "actor": actor, "action": action, "prev": prev}
    ).encode()).hexdigest()
    con.execute("INSERT INTO audit_events(ts,actor,action,payload_hash,prev_hash)"
                " VALUES(?,?,?,?,?)", (ts, actor, action, h, prev))
    con.commit()
