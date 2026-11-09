"""Shared helpers for the exploration notebooks: data loading and UK-time handling only."""

from pathlib import Path

import pandas as pd

UK_TZ = "Europe/London"
DATA_DIR = Path(__file__).resolve().parent.parent / "candidate_data"

TABLES = [
    "imbalance_price",
    "demand_forecast_elexon",
    "wind_forecast_elexon",
    "wind_solar_forecast_embedded",
    "margin_half_hourly",
    "margin_daily",
]


def load(name: str) -> pd.DataFrame:
    """Load one candidate_data parquet table. Timestamps are tz-aware UTC."""
    return pd.read_parquet(DATA_DIR / f"{name}.parquet")


def load_all() -> dict[str, pd.DataFrame]:
    return {name: load(name) for name in TABLES}


def to_uk(ts: pd.Series) -> pd.Series:
    """Convert a UTC timestamp series to UK local time."""
    return ts.dt.tz_convert(UK_TZ)


def settlement_day(period_start: pd.Series) -> pd.Series:
    """UK local calendar date of each half-hour period (the 'day D' of the task)."""
    return to_uk(period_start).dt.date


# Final hold-out: the last 8 weeks of price data (UK days 2026-08-06 .. 2026-09-30).
# Exploration and model selection use only days before this. Touch the test set once, at the end.
TEST_START = pd.Timestamp("2026-08-06", tz=UK_TZ)


def dev_only(df: pd.DataFrame, col: str = "period_start") -> pd.DataFrame:
    """Keep rows whose target period falls before the hold-out."""
    return df[df[col] < TEST_START.tz_convert("UTC")]
