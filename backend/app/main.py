"""Flask API. Thin layer: parse/validate params, call analysis, shape JSON."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request

from . import analysis as an
from .config import DATA_DIR, DEFAULT_CUTOFF, TIMEZONE
from .store import DataNotFound, DataStore, load_store


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _iso(ts) -> str | None:
    return None if pd.isna(ts) else ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_arg(name: str, default=None) -> pd.Timestamp:
    raw = request.args.get(name)
    if raw is None:
        if default is None:
            raise ApiError(f"Missing query parameter '{name}' (YYYY-MM-DD)")
        return pd.Timestamp(default)
    try:
        return pd.Timestamp(pd.to_datetime(raw, format="%Y-%m-%d"))
    except Exception as exc:  # noqa: BLE001
        raise ApiError(f"'{name}' must be a date in YYYY-MM-DD format") from exc


def _cutoff_arg() -> tuple[int, int]:
    try:
        return an.parse_cutoff(request.args.get("cutoff", DEFAULT_CUTOFF))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc


def create_app(data_dir: Path | None = None) -> Flask:
    app = Flask(__name__)
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    cache: dict[str, DataStore] = {}

    def store() -> DataStore:
        if "s" not in cache:
            try:
                cache["s"] = load_store(data_dir)
            except DataNotFound as exc:
                raise ApiError(str(exc), 503) from exc
        return cache["s"]

    def decision_range(s: DataStore) -> tuple[pd.Timestamp, pd.Timestamp]:
        m = s.meta
        if m.get("decision_start") and m.get("decision_end"):
            return pd.Timestamp(m["decision_start"]), pd.Timestamp(m["decision_end"])
        local = s.actuals["startTime"].dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
        return local.min() - pd.Timedelta(days=1), local.max() - pd.Timedelta(days=1)

    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return jsonify({"error": err.message}), err.status

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/meta")
    def meta():
        s = store()
        d0, d1 = decision_range(s)
        return jsonify(
            {
                "source": s.meta.get("source", "unknown"),
                "fetched_at": s.meta.get("fetched_at"),
                "decision_start": d0.strftime("%Y-%m-%d"),
                "decision_end": d1.strftime("%Y-%m-%d"),
                "default_cutoff": DEFAULT_CUTOFF,
                "timezone": TIMEZONE,
                "actual_rows": int(len(s.actuals)),
                "forecast_rows": int(len(s.forecasts)),
            }
        )

    @app.get("/api/decision")
    def decision():
        """The forecast a trader would have seen on `decision_date` at `cutoff`,
        for delivery on decision_date + 1 day."""
        s = store()
        d0, d1 = decision_range(s)
        decision_date = _date_arg("decision_date")
        if not (d0 <= decision_date <= d1):
            raise ApiError(
                f"decision_date must be between {d0:%Y-%m-%d} and {d1:%Y-%m-%d}", 404
            )
        cutoff = _cutoff_arg()
        delivery = decision_date + pd.Timedelta(days=1)

        # Whole range (for the leave-one-out error band) and the selected day.
        all_dec = an.select_decision_forecasts(
            s.forecasts, cutoff, d0 + pd.Timedelta(days=1), d1 + pd.Timedelta(days=1)
        )
        all_df = an.add_actuals(all_dec, s.actuals)
        day = all_df[all_df["delivery_date"] == delivery].sort_values("startTime")
        if day.empty:
            raise ApiError(
                "No forecast had been published before the cut-off for this delivery day.", 404
            )

        band = an.error_band(all_df, exclude_date=delivery)
        series = []
        for r in day.itertuples():
            low = high = None
            if band:
                low = max(0.0, r.forecast - band["q_hi"])   # pessimistic wind outcome
                high = r.forecast - band["q_lo"]            # optimistic wind outcome
            series.append(
                {
                    "startTime": _iso(r.startTime),
                    "publishTime": _iso(r.publishTime),
                    "forecast": an._f(r.forecast),
                    "actual": an._f(r.actual),
                    "error": an._f(r.error),
                    "low": an._f(low),
                    "high": an._f(high),
                }
            )
        f = day["forecast"]
        cutoff_utc = day["cutoff"].iloc[0]
        return jsonify(
            {
                "decision_date": f"{decision_date:%Y-%m-%d}",
                "delivery_date": f"{delivery:%Y-%m-%d}",
                "cutoff_local": request.args.get("cutoff", DEFAULT_CUTOFF),
                "cutoff_utc": _iso(cutoff_utc),
                "summary": {
                    "targets": int(len(day)),
                    "latest_publish_time": _iso(day["publishTime"].max()),
                    "earliest_publish_time": _iso(day["publishTime"].min()),
                    "mean_mw": an._f(f.mean()),
                    "peak_mw": an._f(f.max()),
                    "peak_time": _iso(day.loc[f.idxmax(), "startTime"]),
                    "min_mw": an._f(f.min()),
                    "total_mwh": an._f(f.sum() * 0.5),
                    "actuals_available": bool(day["actual"].notna().any()),
                },
                "band": (
                    {
                        "label": "Likely range (10th-90th percentile of day-ahead errors on other days)",
                        "based_on_points": band["n"],
                    }
                    if band
                    else None
                ),
                "metrics": an.compute_metrics(day),
                "series": series,
            }
        )

    @app.get("/api/accuracy")
    def accuracy():
        s = store()
        d0, d1 = decision_range(s)
        start = _date_arg("start", d0)
        end = _date_arg("end", d1)
        if start > end:
            raise ApiError("'start' must not be after 'end'")
        cutoff = _cutoff_arg()
        one = pd.Timedelta(days=1)
        dec = an.select_decision_forecasts(s.forecasts, cutoff, start + one, end + one)
        df = an.add_actuals(dec, s.actuals)
        days = int((end - start).days) + 1
        return jsonify(
            {
                "start": f"{start:%Y-%m-%d}",
                "end": f"{end:%Y-%m-%d}",
                "cutoff_local": request.args.get("cutoff", DEFAULT_CUTOFF),
                "coverage": {
                    "expected_targets": days * (48 if (s.forecasts["startTime"].dt.minute == 30).any() else 24),
                    "with_forecast": int(len(df)),
                    "with_forecast_and_actual": int(df["error"].notna().sum()),
                },
                "metrics": an.compute_metrics(df),
                "daily": an.daily_table(df),
                "by_hour": an.by_hour_of_day(df),
                "histogram": an.error_histogram(df),
            }
        )

    @app.get("/api/horizon")
    def horizon():
        s = store()
        d0, d1 = decision_range(s)
        start = _date_arg("start", d0)
        end = _date_arg("end", d1)
        one = pd.Timedelta(days=1)
        return jsonify(
            {
                "start": f"{start:%Y-%m-%d}",
                "end": f"{end:%Y-%m-%d}",
                "buckets": an.by_horizon(s.forecasts, s.actuals, start + one, end + one),
            }
        )

    return app
