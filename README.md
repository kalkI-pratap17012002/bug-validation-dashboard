# 🐞 Bug Validation Dashboard

A live Streamlit dashboard for tracking bug validation progress across groups in a Foundations of Computer Security course.

## Features
- **Group Overview** — Per-group validation donuts for security and functionality
- **Rankings** — Sortable leaderboard with configurable columns
- **Action Queue** — Operational backlog for pending validation, pending reviewer response, and pending student rebuttal
- **Student Lookup** — Filter by bug type and discussion state with status + discussion pie charts
- **Group Lookup** — Group-level lookup with reporter identity and matching pie-chart panels
- **Aging/SLA View** — Queue aging bands and SLA mix chart
- **Sheet Deep Links** — Open the exact source row in Google Sheets
- **Auto-refresh + Cache** — Sync every 30 seconds

## Run Locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud Deployment
1. Push this folder to a GitHub repository.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app** and choose:
   - **Repository**: your GitHub repo
   - **Branch**: the branch containing this app
   - **Main file path**: `app.py`
4. Click **Deploy**.

No secrets are required for the current public Google Sheet source.

## Notes
- The app is configured for 30-second sync cadence.
- If a timestamp column is added later, aging/SLA automatically switches to exact time-based hours/days.
