"""Loads the cached Elexon extract (CSV) produced by scripts/fetch_data.py."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class DataNotFound(RuntimeError):
    pass


@dataclass
class DataStore:
    actuals: pd.DataFrame      # startTime, generation
    forecasts: pd.DataFrame    # publishTime, startTime, generation
    meta: dict


def _read(path: Path, time_cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise DataNotFound(
            f"{path.name} not found in {path.parent}. Run `python -m scripts.fetch_data` "
            "(see README) to download the Elexon data."
        )
    df = pd.read_csv(path)
    for c in time_cols:
        df[c] = pd.to_datetime(df[c], utc=True)
    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")
    return df.dropna(subset=["generation"])


def load_store(data_dir: Path) -> DataStore:
    actuals = _read(data_dir / "actuals.csv", ["startTime"])
    forecasts = _read(data_dir / "forecasts.csv", ["startTime", "publishTime"])
    meta_path = data_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"source": "unknown"}
    actuals = actuals.drop_duplicates("startTime", keep="last").sort_values("startTime")
    forecasts = forecasts.drop_duplicates(["startTime", "publishTime"], keep="last")
    return DataStore(actuals.reset_index(drop=True), forecasts.reset_index(drop=True), meta)
