# System Imbalance Price Forecaster

Day-ahead forecasts of the GB System Imbalance Price (SIP, £/MWh) for every half-hour settlement
period of a UK day D, produced at **07:00** and **09:00 UK time on D-1**.

Data: see [`candidate_data/README.md`](candidate_data/README.md). Parquet files are tracked in git;
the CSV copies are git-ignored.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run python -m sip_forecaster backtest                  # development back-test (17 blocks of 28 days) -> outputs/backtest_dev.parquet
uv run python -m sip_forecaster forecast --day 2026-09-30 # both cutoffs: 48 half-hours each, point + 10% + 90% quantiles
uv run python -m sip_forecaster holdout                   # score the final hold-out, once (refuses to overwrite earlier results)
```

`forecast` trains on all days labelled up to D-2 and uses only information available at 07:00 and 09:00 UK on D-1.
The 90% quantile needs `outputs/backtest_dev.parquet` (out-of-sample residuals); run `backtest` first.

## Layout

| Path | Purpose |
| --- | --- |
| `sip_forecaster/` | Forecasting code: features (`features.py`), model (`models.py`), blocked back-test (`backtest.py`), CLI |
| `notebooks/` | Exploration and model comparison (03-19), production parity checks (20) |
| `candidate_data/` | Input data |
| `docs/` | Brief and decision log |
| `Dockerfile`, `docker-compose.yml` | Container run of the forecasting script (build untested) |
| `CLAUDE.md` | Working context for AI-assisted sessions |
