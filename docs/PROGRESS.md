# Progress log

## 2026-11-09
- Repo scaffolded (uv, Docker skeleton, docs). Next: exploratory notebooks in `notebooks/`.
- Open item for price EDA: has the price distribution / daily spread changed over time (possible
  effect of battery growth)? See D-002.

## 2026-11-09 - 01 data audit done
- Prices clean (35,039 rows, 1 missing half-hour on 2026-01-18, fat tails: max 2,900, 1,931 negatives).
- Wind and embedded forecasts are available for ~99% of day D at both cutoffs. Demand forecast full-day
  vintage arrives ~08:48 D-1 (only ~21% of periods at 07:00, ~99% at 09:00). `margin_half_hourly` full-day
  vintage arrives ~12:06 D-1 (after both cutoffs) and only exists from 2025-10-09, so it is of little use.
- Missing `received_at`: embedded wind/solar and margin_daily (use `issued_at`).
- Details in `notebooks/01_data_audit.ipynb`.
- Next: 02 price EDA (shape, spikes, drift per D-002).
