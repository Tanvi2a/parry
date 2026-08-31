"""The window into the office. Run: streamlit run ui/app.py (from repo root)."""
import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Parry", layout="wide")
st.title("Parry — dispute queue")
con = sqlite3.connect("data/out/parry.db")
st.subheader("Disputes (sorted by deadline)")
st.dataframe(pd.read_sql("SELECT * FROM disputes ORDER BY respond_by", con))
st.subheader("Audit log (append-only, hash-chained)")
st.dataframe(pd.read_sql("SELECT * FROM audit_events ORDER BY seq DESC", con))
