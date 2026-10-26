"""Pure analysis functions (no Flask / IO) so they are easy to unit test.

Conventions
-----------
* All timestamps are tz-aware UTC pandas Timestamps; "local" means Europe/London.
* error = forecast - actual  (MW).
    - error > 0  -> over-forecast: less wind than expected, the utility must buy
                    MORE than planned (shortfall risk, usually the costly side).
    - error < 0  -> under-forecast: surplus wind, the utility bought too much.
* A *decision forecast* for a half-hour target is the forecast with the latest
  publishTime that is <= the decision cut-off (default 09:00 UK time on D-1,
  where D is the target's delivery day).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TIMEZONE


def parse_cutoff(value: str) -> tuple[int, int]:
    try:
        hh, mm = value.split(":")
        h, m = int(hh), int(mm)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("cutoff must look like 'HH:MM'") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("cutoff must be a valid time of day")
    return h, m


def select_decision_forecasts(
    forecasts: pd.DataFrame,
    cutoff: tuple[int, int],
    delivery_start,
    delivery_end,
) -> pd.DataFrame:
    """Latest forecast per target available at the day-ahead cut-off.

    forecasts: columns publishTime, startTime, generation (UTC tz-aware).
    delivery_start / delivery_end: inclusive local delivery dates.
    Returns columns: startTime, publishTime, forecast, delivery_date, cutoff.
    """
    f = forecasts.rename(columns={"generation": "forecast"}).copy()
    local = f["startTime"].dt.tz_convert(TIMEZONE)
    f["delivery_date"] = local.dt.tz_localize(None).dt.normalize()
    f = f[
        (f["delivery_date"] >= pd.Timestamp(delivery_start))
        & (f["delivery_date"] <= pd.Timestamp(delivery_end))
    ].copy()
    if f.empty:
        f["cutoff"] = pd.Series(dtype="datetime64[ns, UTC]")
        return f

    h, m = cutoff
    naive_cut = f["delivery_date"] - pd.Timedelta(days=1) + pd.Timedelta(hours=h, minutes=m)
    f["cutoff"] = naive_cut.dt.tz_localize(
        TIMEZONE, ambiguous="NaT", nonexistent="shift_forward"
    ).dt.tz_convert("UTC")

    f = f[f["publishTime"] <= f["cutoff"]]
    f = f.sort_values(["startTime", "publishTime"]).drop_duplicates("startTime", keep="last")
    return f.reset_index(drop=True)


def add_actuals(decision: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Left-join actuals; compute error and lead time (hours)."""
    a = actuals.rename(columns={"generation": "actual"})[["startTime", "actual"]]
    out = decision.merge(a, on="startTime", how="left")
    out["error"] = out["forecast"] - out["actual"]
    out["horizon_h"] = (out["startTime"] - out["publishTime"]).dt.total_seconds() / 3600
    return out


def _f(x):
    """numpy/pandas scalar -> JSON-safe float (None for NaN)."""
    if x is None or pd.isna(x):
        return None
    return round(float(x), 2)


def compute_metrics(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["error"])
    n = int(len(d))
    if n == 0:
        return {"n": 0}
    e, a = d["error"], d["actual"]
    abs_e = e.abs()
    total_actual = a.sum()
    return {
        "n": n,
        "mae": _f(abs_e.mean()),
        "rmse": _f(np.sqrt((e**2).mean())),
        "bias": _f(e.mean()),
        "wape_pct": _f(100 * abs_e.sum() / total_actual) if total_actual > 0 else None,
        "mean_actual": _f(a.mean()),
        "mean_forecast": _f(d["forecast"].mean()),
        "abs_error_p50": _f(abs_e.quantile(0.5)),
        "abs_error_p90": _f(abs_e.quantile(0.9)),
        "abs_error_p95": _f(abs_e.quantile(0.95)),
        "error_quantiles": {
            f"p{int(q * 100):02d}": _f(e.quantile(q)) for q in (0.05, 0.10, 0.50, 0.90, 0.95)
        },
        "overforecast_share_pct": _f(100 * (e > 0).mean()),
    }


def error_band(all_df: pd.DataFrame, exclude_date=None, lo_q=0.10, hi_q=0.90):
    """Empirical quantiles of signed error from OTHER days (leave-one-out, so the
    band shown for a day never uses that day's own outcome)."""
    d = all_df.dropna(subset=["error"])
    if exclude_date is not None:
        d = d[d["delivery_date"] != pd.Timestamp(exclude_date)]
    if len(d) < 48:  # need at least a day's worth to say anything
        return None
    return {
        "q_lo": float(d["error"].quantile(lo_q)),
        "q_hi": float(d["error"].quantile(hi_q)),
        "n": int(len(d)),
    }


def daily_table(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["error"])
    rows = []
    for date, g in d.groupby("delivery_date"):
        m = compute_metrics(g)
        rows.append(
            {
                "delivery_date": date.strftime("%Y-%m-%d"),
                "n": m["n"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "bias": m["bias"],
                "wape_pct": m["wape_pct"],
                "mean_forecast": m["mean_forecast"],
                "mean_actual": m["mean_actual"],
                "forecast_mwh": _f(g["forecast"].sum() * 0.5),
                "actual_mwh": _f(g["actual"].sum() * 0.5),
            }
        )
    return rows


def by_hour_of_day(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["error"]).copy()
    d["hour"] = d["startTime"].dt.tz_convert(TIMEZONE).dt.hour
    out = []
    for hour, g in d.groupby("hour"):
        out.append(
            {
                "hour": int(hour),
                "mae": _f(g["error"].abs().mean()),
                "bias": _f(g["error"].mean()),
                "n": int(len(g)),
            }
        )
    return out


def error_histogram(df: pd.DataFrame, bins: int = 24) -> list[dict]:
    e = df["error"].dropna()
    if e.empty:
        return []
    lim = float(np.ceil(max(abs(e.min()), abs(e.max())) / 100) * 100) or 100.0
    counts, edges = np.histogram(e, bins=bins, range=(-lim, lim))
    return [
        {"from": _f(edges[i]), "to": _f(edges[i + 1]), "count": int(counts[i])}
        for i in range(len(counts))
    ]


def by_horizon(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    delivery_start,
    delivery_end,
    bucket_h: int = 6,
    max_h: int = 48,
) -> list[dict]:
    """Accuracy vs forecast lead time using ALL published forecasts (not just the
    decision one) - shows how much error shrinks as delivery approaches."""
    f = forecasts.rename(columns={"generation": "forecast"}).copy()
    local_date = f["startTime"].dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
    f = f[(local_date >= pd.Timestamp(delivery_start)) & (local_date <= pd.Timestamp(delivery_end))]
    f = add_actuals(f, actuals).dropna(subset=["error"])
    f = f[(f["horizon_h"] >= 0) & (f["horizon_h"] < max_h)]
    if f.empty:
        return []
    f["bucket"] = (f["horizon_h"] // bucket_h * bucket_h).astype(int)
    out = []
    for b, g in f.groupby("bucket"):
        out.append(
            {
                "from_h": int(b),
                "to_h": int(b + bucket_h),
                "mae": _f(g["error"].abs().mean()),
                "bias": _f(g["error"].mean()),
                "n": int(len(g)),
            }
        )
    return out
