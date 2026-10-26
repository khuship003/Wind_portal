"""Download the Elexon BMRS extracts needed by the app and cache them as CSV.

    cd backend && python -m scripts.fetch_data            # defaults: Jan 2026 decisions

Why a cache instead of live calls? WINDFOR holds many overlapping forecast
vintages (one per publishTime), so a month is tens of thousands of rows. Fetching
that per page-view would be slow and would hammer a public API; the analysis
period is also fixed (January 2026), so a one-off snapshot is the right shape.

Scope: "purchase decisions made in January 2026" => decision dates 1-31 Jan,
delivery dates 2 Jan - 1 Feb. Change with --decision-start / --decision-end.

NOTE: field names/params follow the public BMRS v1 docs. If Elexon changes them
the script fails loudly (see `_require`) rather than silently writing bad data.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
TIMEOUT = 90


def get_json(url: str, params: dict, retries: int = 4) -> list[dict]:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            return body["data"] if isinstance(body, dict) and "data" in body else body
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise
            wait = 2**attempt
            print(f"  retry {attempt}/{retries - 1} after error: {exc} (sleep {wait}s)")
            time.sleep(wait)
    return []


def _require(df: pd.DataFrame, cols: list[str], what: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if df.empty or missing:
        raise SystemExit(
            f"{what}: expected columns {cols}, got {list(df.columns)} ({len(df)} rows). "
            "Check the endpoint/params against the BMRS docs."
        )


def fetch_actuals(d_from, d_to) -> pd.DataFrame:
    """FUELHH stream, WIND only. Chunked by 7 days (API range limit)."""
    rows, cur = [], d_from
    while cur <= d_to:
        end = min(cur + timedelta(days=6), d_to)
        print(f"FUELHH {cur:%Y-%m-%d} -> {end:%Y-%m-%d}")
        rows += get_json(
            f"{BASE}/FUELHH/stream",
            {
                "settlementDateFrom": f"{cur:%Y-%m-%d}",
                "settlementDateTo": f"{end:%Y-%m-%d}",
                "fuelType": "WIND",
                "format": "json",
            },
        )
        cur = end + timedelta(days=1)
    df = pd.DataFrame(rows)
    _require(df, ["fuelType", "startTime", "generation"], "FUELHH")
    df = df[df["fuelType"] == "WIND"][["startTime", "generation"]]
    return df.drop_duplicates("startTime", keep="last").sort_values("startTime")


def fetch_forecasts(p_from: datetime, p_to: datetime) -> pd.DataFrame:
    """WINDFOR stream filtered by publishTime. Chunked by 1 day."""
    rows, cur = [], p_from
    while cur < p_to:
        end = min(cur + timedelta(days=1), p_to)
        print(f"WINDFOR publish {cur:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M}")
        rows += get_json(
            f"{BASE}/WINDFOR/stream",
            {
                "publishDateTimeFrom": cur.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json",
            },
        )
        cur = end
    df = pd.DataFrame(rows)
    _require(df, ["publishTime", "startTime", "generation"], "WINDFOR")
    return df[["publishTime", "startTime", "generation"]].drop_duplicates(
        ["publishTime", "startTime"], keep="last"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--decision-start", default="2026-01-01")
    ap.add_argument("--decision-end", default="2026-01-31")
    ap.add_argument("--max-horizon-h", type=int, default=48,
                    help="drop forecasts published more than N hours before their target")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
    a = ap.parse_args()

    d0 = datetime.strptime(a.decision_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    d1 = datetime.strptime(a.decision_end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    deliv_from, deliv_to = d0 + timedelta(days=1), d1 + timedelta(days=1)

    # Actuals: pad one day each side so timezone edges are covered.
    actuals = fetch_actuals(deliv_from - timedelta(days=1), deliv_to + timedelta(days=1))
    # Forecasts: published from one day before first decision to end of last decision day.
    forecasts = fetch_forecasts(d0 - timedelta(days=1), d1 + timedelta(days=1))

    st = pd.to_datetime(forecasts["startTime"], utc=True)
    pt = pd.to_datetime(forecasts["publishTime"], utc=True)
    horizon = (st - pt).dt.total_seconds() / 3600
    keep = (horizon >= 0) & (horizon <= a.max_horizon_h) & (st >= deliv_from) & (
        st < deliv_to + timedelta(days=1)
    )
    forecasts = forecasts[keep].sort_values(["startTime", "publishTime"])

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    actuals.to_csv(out / "actuals.csv", index=False)
    forecasts.to_csv(out / "forecasts.csv", index=False)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "source": "elexon",
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "decision_start": a.decision_start,
                "decision_end": a.decision_end,
                "max_horizon_h": a.max_horizon_h,
                "actual_rows": int(len(actuals)),
                "forecast_rows": int(len(forecasts)),
            },
            indent=2,
        )
    )
    print(f"\nWrote {len(actuals)} actual rows and {len(forecasts)} forecast rows to {out}")
    print("Sample forecasts:\n", forecasts.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
