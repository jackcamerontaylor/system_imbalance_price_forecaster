"""Raw data loading and UK-time helpers. Raw timestamps are UTC; 'day' and run times are UK local."""

from pathlib import Path

import pandas as pd

UK_TZ = "Europe/London"
DATA_DIR = Path(__file__).resolve().parent.parent / "candidate_data"
OUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

TABLES = ["imbalance_price", "demand_forecast_elexon", "wind_forecast_elexon",
          "wind_solar_forecast_embedded", "margin_daily"]

# Final hold-out (D-003): UK days 2026-08-06 .. 2026-09-30. Exploration and model selection used only earlier days.
TEST_START_DAY = pd.Timestamp("2026-08-06")

# England and Wales bank holidays, listed by hand (no extra dependency); they cover the data range.
BANK_HOLIDAYS = pd.to_datetime([
    "2024-12-25", "2024-12-26",
    "2025-01-01", "2025-04-18", "2025-04-21", "2025-05-05", "2025-05-26", "2025-08-25", "2025-12-25", "2025-12-26",
    "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04", "2026-05-25", "2026-08-31"])


def load_tables(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    return {n: pd.read_parquet(data_dir / f"{n}.parquet") for n in TABLES}


def to_uk(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_convert(UK_TZ)


def uk_day(ts: pd.Series) -> pd.Series:
    """UK calendar day (tz-naive midnight) of each UTC timestamp."""
    return to_uk(ts).dt.tz_localize(None).dt.normalize()


def day_grid(days: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """All half-hour period starts (UTC) of the given UK days: 46/48/50 per day, from the calendar, not from the data."""
    parts = []
    for d in days:
        start = pd.Timestamp(d).tz_localize(UK_TZ).tz_convert("UTC")
        end = pd.Timestamp(d + pd.Timedelta(days=1)).tz_localize(UK_TZ).tz_convert("UTC")
        parts.append(pd.date_range(start, end, freq="30min", inclusive="left"))
    return parts[0].append(parts[1:]) if len(parts) > 1 else parts[0]
