# Video script (max 10 min total)  – record screen + voice, upload as UNLISTED on YouTube

## Part 1 – Customer pitch (≤ 5 min)  "Pilot results"
**0:00 Hook (30s).** "Every morning your desk commits to tomorrow's power purchase before you know what the wind will do. Two questions decide how much expensive thermal you buy: *what's the best wind forecast I can see at decision time?* and *how wrong could it be?* This portal answers both."
**0:30 Decision view (90s).** Pick a decision day (e.g. a windy day). Point out: delivery day, "latest forecast issued at …" banner, KPIs (avg/peak/lowest wind), forecast line with shaded likely range. Toggle cut-off 09:00 → 07:00 to show how the forecast version changes. Reveal actuals line: "here's what really happened".
**2:00 Accuracy view (120s).** KPIs: MAE, bias, P90 shortfall. Read the callout aloud in business terms ("1 half-hour in 10 wind is X MW below forecast → hold that much reserve/hedge"). Show hour-of-day and lead-time charts: "waiting for a fresher forecast helps by …" (quote the real numbers).
**4:00 Value + next steps (60s).** Quantified error → sized buffers; auditable (point-in-time); next: add demand & price data, live feed, probabilistic forecasts. Close with a concrete ask (extend pilot).
*Tip: use REAL numbers from the Elexon data; practise once so it lands under 5 min.*

## Part 2 – Tech-lead review (≤ 5 min)
**0:00 Overview (45s).** Architecture diagram from docs/DESIGN.md; repo layout; deployed URL.
**0:45 Analysis logic (90s).** Open `backend/app/analysis.py` → `select_decision_forecasts` (explain the cut-off and why it avoids look-ahead), `compute_metrics`, `error_band` (leave-one-out). State assumptions (cut-off 09:00, Jan-decision scope).
**2:15 Data + API (60s).** `scripts/fetch_data.py` (endpoints, chunking, fail-loud schema check, why snapshot); `main.py` routes and error codes.
**3:15 Frontend (45s).** Components, `api.js`, how the band is drawn.
**4:00 Practices (60s).** Tests (run them live), Docker compose, Vercel config, AI-tool disclosure, limitations + next steps.
