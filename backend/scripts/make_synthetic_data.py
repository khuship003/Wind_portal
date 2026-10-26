"""Generate SYNTHETIC wind data in the same shape as the real extract.

For unit tests and local UI development only - NOT real Elexon data. The output
meta.json carries source="synthetic" so the UI shows a warning banner.

    python -m scripts.make_synthetic_data --out /tmp/synth
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def generate(decision_start="2026-01-01", decision_end="2026-01-31", seed=7):
    rng = np.random.default_rng(seed)
    d0 = pd.Timestamp(decision_start, tz="UTC")
    d1 = pd.Timestamp(decision_end, tz="UTC")
    t_start = d0 - pd.Timedelta(days=1)
    t_end = d1 + pd.Timedelta(days=3)
    idx = pd.date_range(t_start, t_end, freq="30min", inclusive="left")

    # Smooth AR(1) "true" wind between ~500 and ~14000 MW.
    x = np.zeros(len(idx))
    for i in range(1, len(idx)):
        x[i] = 0.995 * x[i - 1] + rng.normal(0, 0.12)
    actual = np.clip(7000 + 4500 * x / (x.std() + 1e-9), 300, 14500)
    actuals = pd.DataFrame({"startTime": idx, "generation": actual.round(0)})

    lookup = dict(zip(actuals["startTime"], actuals["generation"]))
    rows = []
    for pub in pd.date_range(d0 - pd.Timedelta(days=1), d1 + pd.Timedelta(days=1), freq="h", inclusive="left"):
        for h in range(0, 49):
            tgt = pub + pd.Timedelta(hours=h)
            for half in (0, 30):
                st = tgt + pd.Timedelta(minutes=half)
                true = lookup.get(st)
                if true is None:
                    continue
                sigma = 250 + 90 * h                    # error grows with lead time
                rows.append((pub, st, max(0.0, round(true + rng.normal(0, sigma) + 60, 0))))
    forecasts = pd.DataFrame(rows, columns=["publishTime", "startTime", "generation"])
    return actuals, forecasts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--decision-start", default="2026-01-01")
    ap.add_argument("--decision-end", default="2026-01-31")
    a = ap.parse_args()
    actuals, forecasts = generate(a.decision_start, a.decision_end)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    actuals.to_csv(out / "actuals.csv", index=False)
    forecasts.to_csv(out / "forecasts.csv", index=False)
    (out / "meta.json").write_text(
        json.dumps(
            {"source": "synthetic", "fetched_at": None,
             "decision_start": a.decision_start, "decision_end": a.decision_end}, indent=2)
    )
    print(f"synthetic data written to {out} ({len(actuals)} actual, {len(forecasts)} forecast rows)")


if __name__ == "__main__":
    main()
