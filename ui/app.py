"""Parry dashboard: queue by deadline, case view with the contradiction
highlight, metrics, and the audit log with live chain verification.
Run from repo root:  streamlit run ui/app.py
"""
import datetime as dt
import json
import pathlib
import sys
import time

import pandas as pd
import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from api.audit import log as audit_log  # noqa: E402
from engine.checklists import completeness  # noqa: E402
from engine.contradictions import CACHE_DIR  # noqa: E402
from engine.retrieve import case_file  # noqa: E402
from packet.build import build as build_packet  # noqa: E402

st.set_page_config(page_title="Parry", layout="wide", page_icon="🛡️")
GOLD, FIGHT, ACCEPT, MUTED = "#C9A227", "#C1603F", "#7FAE88", "#A79E8C"
VCOLOR = {"FIGHT": FIGHT, "ACCEPT": ACCEPT, "ABSTAIN": GOLD,
          "EXPIRED": "#777777", "UNDECIDED": MUTED}

con = db.connect()
now = int(time.time())


def when(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%d %b, %H:%M")


# ---------------- sidebar ----------------
st.sidebar.markdown("## 🛡️ Parry")
st.sidebar.caption("Auto-responders fight what they can. "
                   "Parry fights what it should.")
page = st.sidebar.radio("View", ["Queue", "Case", "Metrics", "Audit log"])
kill = st.sidebar.toggle("Kill switch",
                         value=st.session_state.get("kill", False),
                         help="Halts all automation; the flip itself is "
                              "audit-logged.")
if kill != st.session_state.get("kill", False):
    audit_log(con, "human",
              f"kill_switch:{'engaged' if kill else 'released'}")
    st.session_state["kill"] = kill
if kill:
    st.sidebar.error("All automation halted")

rows = con.execute("""
    SELECT d.id, d.reason_code, d.amount, d.respond_by, dec.verdict,
           dec.p_win, dec.ev_paise, dec.mode
    FROM disputes d LEFT JOIN decisions dec ON dec.dispute_id = d.id
    ORDER BY d.respond_by""").fetchall()
ids = [r[0] for r in rows]
vc = pd.Series([r[4] or "UNDECIDED" for r in rows]).value_counts()
st.sidebar.caption(" · ".join(f"{k} {v}" for k, v in vc.items()))

# ---------------- queue ----------------
if page == "Queue":
    st.title("Dispute queue")
    st.caption("Sorted by respond_by. SLA: 🔴 <36h · 🟠 <72h · 🟢 ok · "
               "⚫ expired")
    data = []
    for (i, rc, amt, rb, v, p, ev, mode) in rows:
        hrs = (rb - now) / 3600
        sla = ("⚫" if hrs < 0 else "🔴" if hrs < 36
               else "🟠" if hrs < 72 else "🟢")
        data.append(dict(SLA=sla, id=i, reason=rc,
                         amount=f"₹{amt / 100:,.0f}",
                         respond_by=when(rb),
                         verdict=v or "—",
                         mode=mode or "—",
                         p_win=(f"{p:.2f}" if p is not None else "—"),
                         EV=(f"₹{ev / 100:,.0f}" if ev is not None
                             else "—")))
    st.dataframe(pd.DataFrame(data), use_container_width=True,
                 hide_index=True, height=560)
    pick = st.selectbox("Open case →", ids,
                        index=ids.index(st.session_state.get("case",
                                                             ids[0])))
    st.session_state["case"] = pick
    st.caption("Now switch to the **Case** view in the sidebar.")

# ---------------- case ----------------
elif page == "Case":
    cid = st.selectbox("Case", ids,
                       index=ids.index(st.session_state.get("case",
                                                            ids[0])))
    st.session_state["case"] = cid
    cf = case_file(con, cid)
    d = cf["dispute"]
    dec = con.execute("SELECT verdict, p_win, ev_paise, mode, features "
                      "FROM decisions WHERE dispute_id=?",
                      (cid,)).fetchone()
    verdict = dec[0] if dec else "UNDECIDED"
    p, ev, mode = ((dec[1], dec[2], dec[3]) if dec else (None, None, "—"))
    rationale = (json.loads(dec[4]).get("rationale", "")
                 if dec and dec[4] else "run engine.run_decisions first")

    st.markdown(
        f"<div style='background:{VCOLOR[verdict]}22;border:1px solid "
        f"{VCOLOR[verdict]};border-radius:10px;padding:14px 20px'>"
        f"<span style='font-size:26px;font-weight:700;color:"
        f"{VCOLOR[verdict]}'>{verdict}</span>"
        f"<span style='color:{MUTED}'> · {mode} · {rationale}</span></div>",
        unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Amount", f"₹{d['amount'] / 100:,.0f}")
    c2.metric("p(win)", f"{p:.2f}" if p is not None else "—")
    c3.metric("EV", f"₹{ev / 100:,.0f}" if ev is not None else "—")
    hrs = (d["respond_by"] - now) / 3600
    c4.metric("Deadline", when(d["respond_by"]),
              delta=f"{hrs:.0f}h left" if hrs > 0 else "EXPIRED",
              delta_color="normal" if hrs > 36 else "inverse")

    b1, b2 = st.columns(2)
    if b1.button("Generate evidence packet", type="primary",
                 use_container_width=True):
        path = build_packet(con, cid)
        audit_log(con, "parry", f"packet_generated:{cid}")
        st.success(f"Packet written: {path}")
        b1.download_button("Download packet (HTML)",
                           data=path.read_text(),
                           file_name=f"{cid}_representment.html",
                           use_container_width=True)
    if b2.button("Submit representment (simulated)",
                 use_container_width=True):
        if st.session_state.get("kill"):
            st.error("Kill switch engaged — all automation halted.")
        elif verdict == "EXPIRED":
            st.error("Deadline lockout: past respond_by — Parry will "
                     "never submit this case. No override exists.")
        elif verdict != "FIGHT":
            st.warning(f"Verdict is {verdict}; only FIGHT cases submit.")
        else:
            audit_log(con, "human", f"submit_simulated:{cid}:{mode}")
            st.success("Submitted (simulated). Audit entry written.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Support transcript")
        exhibits = []
        cache = CACHE_DIR / f"{cid}.json"
        if cache.exists():
            exhibits = json.loads(cache.read_text()).get("exhibits", [])
        msgs = cf["chat"]["messages"] if cf["chat"] else []
        for m in msgs:
            text = m["text"]
            for e in exhibits:
                if (e["ts"] == m["ts"] and e["source"] == m["sender"]
                        and e["quote"] in text):
                    text = text.replace(
                        e["quote"],
                        f"<mark style='background:{GOLD};color:#12100C;"
                        f"padding:1px 6px;border-radius:5px;font-weight:600'>"
                        f"{e['quote']}</mark>")
            align = "left" if m["sender"] == "customer" else "right"
            border = GOLD if m["sender"] == "customer" else "#3A342A"
            st.markdown(
                f"<div style='text-align:{align};margin:6px 0'>"
                f"<span style='display:inline-block;background:#1C1812;"
                f"border:1px solid {border};border-radius:10px;"
                f"padding:8px 14px;max-width:85%'>"
                f"<b style='color:{MUTED};font-size:11px'>"
                f"{m['sender']} · {when(m['ts'])}</b><br>{text}"
                f"</span></div>", unsafe_allow_html=True)
        if exhibits:
            st.subheader("Verified exhibits (L2)")
            for e in exhibits:
                st.markdown(f"- **[{e['type']}]** “{e['quote']}” "
                            f"<span style='color:{MUTED}'>— {e['source']} "
                            f"@ {when(e['ts'])} · {e['explanation']}</span>",
                            unsafe_allow_html=True)
    with right:
        st.subheader("Evidence checklist (L1)")
        c, breakdown = completeness(cf)
        st.markdown(f"Completeness **c = {c}**")
        st.dataframe(pd.DataFrame(breakdown), hide_index=True,
                     use_container_width=True)
        st.subheader("Authentication")
        a = cf["auth"]
        st.markdown(f"OTP **{a['otp_result']}** · 3DS "
                    f"**{a['three_ds_result']}** · device known "
                    f"**{'yes' if a['device_known'] else 'no'}** · prior "
                    f"orders **{cf['customer']['prior_orders']}**")
        if cf["shipment"]:
            s = cf["shipment"]
            st.subheader("Shipment")
            st.markdown(f"{s['carrier']} · **{s['status']}** · POD "
                        f"**{'on file' if s['pod_url'] else 'MISSING'}** · "
                        f"events: {' → '.join(s['events'])}")

# ---------------- metrics ----------------
elif page == "Metrics":
    st.title("Metrics")
    rep_path = pathlib.Path("data/out/model_report.json")
    if rep_path.exists():
        rep = json.loads(rep_path.read_text())
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Model — small enough to print")
            st.caption(f"LogisticRegression · {rep['n_train']} train cases "
                       f"· CV accuracy@0.5 = {rep['cv_accuracy_at_0p5']}")
            st.dataframe(pd.DataFrame(
                dict(feature=list(rep["coefficients"].keys()),
                     coefficient=list(rep["coefficients"].values()),
                     no_l2_ablation=list(
                         rep["ablation_no_l2_coefficients"].values()))),
                hide_index=True, use_container_width=True)
        with c2:
            st.subheader("Calibration (5-fold CV, train)")
            st.dataframe(pd.DataFrame(rep["calibration_buckets"]),
                         hide_index=True, use_container_width=True)
    ev_path = pathlib.Path("data/out/eval.json")
    if ev_path.exists():
        ev = json.loads(ev_path.read_text())
        st.subheader("Frozen held-out evaluation (60 cases)")
        st.json(ev)
    else:
        st.info("The frozen held-out evaluation runs in Phase 7. This "
                "panel will then show precision & recall of FIGHT, "
                "false-positive cost in ₹, net ₹ vs accept-all and "
                "fight-all, and the --no-l2 ablation row.")

# ---------------- audit ----------------
else:
    st.title("Audit log")
    ev = con.execute("SELECT seq, ts, actor, action, payload_hash, "
                     "prev_hash FROM audit_events ORDER BY seq").fetchall()
    intact = all(ev[i][5] == ev[i - 1][4] for i in range(1, len(ev)))
    intact = intact and (not ev or ev[0][5] == "genesis")
    if intact:
        st.success(f"Hash chain intact ✓ — {len(ev)} entries, each "
                   f"fingerprinting the one before it")
    else:
        st.error("Hash chain BROKEN — history has been tampered with")
    df = pd.DataFrame(ev, columns=["seq", "ts", "actor", "action",
                                   "payload_hash", "prev_hash"])
    st.dataframe(df.iloc[::-1], hide_index=True, use_container_width=True,
                 height=560)
