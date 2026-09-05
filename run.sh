#!/usr/bin/env bash
# Parry -- one-command launch for judges. No API key needed: the dataset,
# the verified LLM cache, the trained models and the frozen eval all ship
# in this repo. Requires Python 3.11+.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
echo "Starting Parry API on :8000 (interactive docs at /docs)..."
uvicorn api.main:app --port 8000 > /tmp/parry_api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
sleep 2
echo "Replaying a seeded dispute through the webhook:"
python api/simulator.py disp_0015 || true
echo "Opening the dashboard on :8501 (Ctrl+C stops everything)..."
streamlit run ui/app.py
