# Wind Forecast Portal – day-ahead buying support (pilot)

Web app that helps a GB utility's day-ahead desk (1) see the **latest wind forecast available at decision time** and (2) **quantify forecast accuracy** using Elexon BMRS data (`FUELHH` actuals, `WINDFOR` forecasts; national wind only).

**Live app:** https://wind-portal-5pb2.vercel.app  ·  **Video:** (https://youtu.be/1uJLhMkUpX4) ·  

**AI disclosure:** I used an AI assistant (Claude by Anthropic) to help generate code and documentation. I reviewed the code, ran the tests, ran the app locally and in Docker, and deployed it myself, and I can explain the design decisions in the accompanying video.

## Repo layout
```
api/index.py              Vercel serverless entrypoint (wraps the Flask app)
backend/app/analysis.py   Pure analysis: decision-time forecast selection, metrics, bands
backend/app/main.py       Flask routes: /api/meta /decision /accuracy /horizon /health
backend/app/store.py      Loads cached CSVs
backend/app/config.py     Config (DATA_DIR, DEFAULT_CUTOFF)
backend/scripts/fetch_data.py          Downloads Elexon data -> backend/data/*.csv + meta.json
backend/scripts/make_synthetic_data.py FAKE data for tests / UI dev only
backend/tests/            unittest suite (analysis + API)
backend/data/             Data snapshot (created by fetch_data.py; commit it for deployment)
frontend/                 React (Vite + Recharts) UI, Dockerfile, nginx.conf
docs/DESIGN.md            Assumptions, design decisions, limitations
docs/VIDEO_SCRIPT.md      Outline for the two-part demo video
docker-compose.yml, vercel.json, requirements.txt
```

## Quick start
### 1. Get the data (needs internet, ~minutes)
```bash
pip install -r requirements.txt
cd backend
python -m scripts.fetch_data            # decisions 1–31 Jan 2026 (delivery 2 Jan–1 Feb)
```
Check the printed row counts and sample, then commit `backend/data/*` (required for the Vercel deployment).

### 2a. Run with Docker
```bash
docker compose up --build        # UI: http://localhost:8080   API: http://localhost:8000/api/health
```
### 2b. Run without Docker
```bash
cd backend && gunicorn -b 0.0.0.0:8000 "app.main:create_app()"     # or: flask --app app.main:create_app run -p 8000
cd frontend && npm install && npm run dev                          # http://localhost:5173 (proxies /api)
```
### Tests
```bash
cd backend && python -m unittest discover -s tests -t . -v
```
### UI development without real data
`python -m scripts.make_synthetic_data --out /tmp/synth && DATA_DIR=/tmp/synth gunicorn ...` – the UI shows a red "not real data" banner.

## Deploy to Vercel
1. Push this repo to GitHub (use an anonymous repo name), with `backend/data/` committed.
2. Vercel → *Add New Project* → import repo, leave root as `/` (settings come from `vercel.json`).
3. Open the deployment URL in incognito and check `/api/health` and the UI, then paste the URL above.

## Method in one paragraph
For delivery day D, the **decision forecast** for each half-hour is the one with the latest `publishTime` ≤ cut-off on D-1 (default 09:00 UK, configurable). Error = forecast − actual (positive ⇒ less wind than forecast ⇒ more to buy). We report MAE, RMSE, bias, WAPE, error percentiles, error by hour of day and by lead time, and draw a leave-one-out 10–90% range around each day's forecast. Assumptions and limitations: `docs/DESIGN.md`.
