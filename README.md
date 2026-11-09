# System Imbalance Price Forecaster

Day-ahead forecasts of the GB System Imbalance Price (SIP, £/MWh) for every half-hour settlement
period of a UK day D, produced at **07:00** and **09:00 UK time on D-1**.

Data: see [`candidate_data/README.md`](candidate_data/README.md). Parquet files are tracked in git;
the CSV copies are git-ignored.

## Setup

```bash
uv sync
```

## Layout

| Path | Purpose |
| --- | --- |
| `notebooks/` | Exploration |
| `candidate_data/` | Input data |
| `docs/` | Brief and decision log |
| `Dockerfile`, `docker-compose.yml` | Container run (to be wired to the forecasting script) |
| `CLAUDE.md` | Working context for AI-assisted sessions |
