# Design notes (for the technical review)

## Problem → product mapping
| Client need | Product answer |
|---|---|
| "Latest forecast available when we must decide" | **Decision view**: for a chosen decision day + cut-off time, show, for each half-hour of the next delivery day, the forecast with the latest `publishTime` ≤ cut-off. |
| "Quantify forecast accuracy to factor error into decisions" | **Accuracy view**: MAE, RMSE, bias, WAPE, error percentiles, error by hour-of-day, by lead time, distribution; plus a leave-one-out "likely range" band on the Decision chart. |

## Key modelling decisions (and assumptions to confirm with the client)
1. **Scope = "decisions made in January 2026"** → decision days 1–31 Jan, delivery days 2 Jan–1 Feb. (The brief is ambiguous: the alternative reading is delivery days in January. Change with `--decision-start/--decision-end` on the fetch script.)
2. **Cut-off = 09:00 UK on D-1** (configurable, UI + `DEFAULT_CUTOFF`). EPEX GB day-ahead gate closure is commonly quoted around 09:20 UK; 09:00 leaves margin. *Needs client confirmation.*
3. **"Latest forecast available"** = max `publishTime` ≤ cut-off, per target `startTime`. This is the point-in-time-correct choice; using the newest forecast in the file would leak information the buyer didn't have.
4. **Error sign** = forecast − actual. Positive means wind undershot, i.e. the utility must buy more; this is the costly side, so we surface the P90 "shortfall" explicitly.
5. **Metrics**: MAE (typical miss), RMSE (penalises large misses), bias (systematic), WAPE (scale-free; used instead of MAPE because wind is near 0 at times and MAPE explodes). Percentiles because buying decisions care about tails, not averages.
6. **Likely-range band** = forecast shifted by the 10th/90th percentile of day-ahead errors on *other* days (leave-one-out, no look-ahead). It is empirical and unconditional (it ignores that error depends on wind level/season) – with one month of data, anything fancier would be overfitting. Called out as a limitation.
7. **Lead-time analysis** uses every forecast run (0–48 h before target) to show how much accuracy improves closer to delivery.

## Out of scope by brief
No demand, price, or other generation data → the app cannot compute the actual MWh to buy, only the wind input and its uncertainty.

## Architecture
```
Elexon BMRS ──(scripts/fetch_data.py, one-off)──► backend/data/*.csv + meta.json
                                                        │
React (Vite, Recharts) ──/api/*──► Flask (app/main.py) ──► app/analysis.py (pure pandas)
```
* **Why a cached snapshot, not live calls:** WINDFOR returns many overlapping forecast vintages (tens of thousands of rows for a month); the period is fixed; Vercel serverless functions have short time limits; and it makes the app deterministic and fast. Trade-off: a refresh requires re-running the script (live ingestion is the obvious next step).
* **`analysis.py` is pure** (DataFrames in, dicts out) so it is unit-tested without Flask; `main.py` only validates and shapes JSON.
* **Honesty guard:** `meta.json` records the data source; the UI shows a red banner if it isn't `elexon`.
* **Errors:** invalid params → 400, outside range / no forecast → 404, missing data → 503 with a fix hint.

## Tests (`cd backend && python -m unittest discover -s tests -t .`)
Cut-off selection (boundary inclusive, later vintages excluded), metric values on hand-computed cases, leave-one-out band, cutoff parsing, API contract and validation, lead-time monotonicity (on synthetic data).

## Known limitations / next steps
* Single month; no seasonality, no wind-level-dependent error model.
* Snapshot not live; add scheduled ingestion + a DB.
* No auth (internal pilot).
* WINDFOR/FUELHH query params follow the public docs but were not exercised against the live API in the build environment – first run of `fetch_data` prints diagnostics and fails loudly on schema mismatch.
