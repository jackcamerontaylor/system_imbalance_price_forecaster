# Day-ahead GB System Imbalance Price forecast: method, results and limits

This report summarises the whole project. The decision log is `docs/DECISIONS.md`, the dated working log is
`docs/PROGRESS.md`, and every claim below traces to a notebook in `notebooks/` (numbers in brackets give the notebook).

## 1. Task and data

For every half-hour settlement period of a UK day D, forecast the System Imbalance Price (SIP, £/MWh) as it could have
been forecast at **07:00 and at 09:00 UK time on D-1**. Inputs are public: price history, NESO/Elexon demand forecasts,
Elexon wind forecasts, embedded wind and solar forecasts, and daily operating-margin forecasts (1 October 2024 to
30 September 2026, `candidate_data/README.md`).

What the audit found (01, 02, 03):

- Prices are clean (one missing half-hour, 2026-01-18) but have fat tails (maximum £2,900, about 5.5% negative) and a rising level
  (median about £66-76 in mid/late 2025, about £113 by July 2026). Own-price persistence is weak (correlation 0.16 at one day).
- Forecast tables keep several vintages per period. Only the latest vintage available at the cutoff may be used. At 07:00 the demand forecast is
  available for only 21% of periods (the full-day vintage arrives about 08:48); at 09:00 it is available for 99%. Wind and embedded
  forecasts are available at both cutoffs (99.5%).
- `margin_half_hourly` (published about 12:06 on D-1, only from October 2025) arrives after both cutoffs and is not used.

## 2. How results were measured

- **No look-ahead.** Every feature uses only information available at the cutoff (latest vintage with `received_at`, else `issued_at`, at or before the
  cutoff; prices of D-2 and earlier plus the 24 hours ending one hour before the cutoff; margin publications dated D-2 or earlier). This was tested in
  the notebooks (05, deliberately wrong cutoffs are caught) and again for the production code by rebuilding features from tables truncated at the cutoff (20).
- **Hold-out (D-003).** The last 8 weeks (UK days 2026-08-06 to 2026-09-30, 56 days) were not used for any exploration or model selection, and were
  scored once, at the end.
- **Development folds (D-007).** 17 chronological blocks of 28 days tiled back from the end of the development period; each block is predicted by a
  model trained on days up to D-2 of its first day. Models are compared with the baseline fold by fold (paired), because the fold-to-fold spread of
  MAE is large (standard deviation about 7 on a mean of 30). Neighbouring folds are not independent, so the standard errors quoted are optimistic.
- **Metrics (D-004).** Because the value of the forecast is in the extreme half-hours, the headline is the **within-day top-8 / bottom-8 hit rate**: the share of the 8
  periods the forecast ranks highest (lowest) in a day that are among the actual 8 highest (lowest); random choice scores 0.167. Also reported:
  pinball loss at 10% and 90%, MAE on the actual top and bottom decile, and MAE, RMSE and bias.
- **Baseline.** The median price of the same clock time over D-29..D-2 (`ref28`), which beat all simpler references (04). Its quantile version
  (empirical 10%/90% of the same window) is the quantile baseline.

## 3. What was tried and what it showed

| # | Question | Result |
| --- | --- | --- |
| 04 | Which simple reference is best? | 28-day same-period median (MAE 31.4, RMSE 63.5, 659 dev days). Longer look-back beats recency. It already ranks the day's periods better than chance (picks 45% of the top-8 and 33% of the bottom-8). |
| 06 | Fold design and metrics | 17 folds; metrics tested on oracle / reversed / noise / constant forecasts. Baseline on the folds: MAE 30.2, RMSE 42.2, hit 0.462 / 0.322. The baseline quantiles under-cover (13.1% of prices below the 10% quantile, 13.8% above the 90%). |
| 07-09 | Gradient boosting (GBM) on forecasts plus calendar plus history | Gain over the baseline: MAE -1.4 to -1.6, RMSE -3.1 to -3.4, hit +0.03 / +0.04, stable across 12 settings. History features alone are worse than the baseline (overfitting). A deviation-from-baseline target is no better than the direct price. The GBM here is deterministic, so seeds do not matter. |
| 10-13 | Why do models under-forecast when prices rise? | The validation mean is below the median, so this is a genuine under-forecast, concentrated in the recent high-price folds, and it comes from the price-history terms and absolute weather levels (which carry seasonal information the reference already has), not from the reference. Huber loss matches the GBM; squared-error ridge does not beat the baseline. |
| 14 | Anomaly features (forecast minus its own D-29..D-2 mean) | They fix the level in recent folds but lose the within-day ranking gain. |
| 15 | Two-part model: daily level from anomalies, ranking from absolute inputs | A daily level model works out of sample (correlation 0.67 with the day's mean deviation from the reference; it removes about 40% of that deviation's variance). Keeping the ordering of the absolute-input model and replacing its level gives the best result on all metrics together (MAE -2.06 against the baseline, hit +0.032 / +0.049). |
| 16 | 07:00 against 09:00, and one combined or two separate models | The difference between the cutoffs is almost entirely the demand forecast. A combined model with a cutoff indicator is not better than two separate ones, so two separate models are used (07:00 without demand inputs). |
| 17 | Quantile forecasts | The 10% quantile is predictable (pinball -2.4 against the baseline); the 90% quantile is not, and direct quantile GBMs under-cover the upper tail in the recent folds. Ranking by a quantile does not beat ranking by the point forecast. |
| 18 | Which model family, or a blend | An equal-weight average of Huber and GBM shapes is best or tied at both cutoffs (09:00 MAE -2.23, 07:00 -1.85 against the baseline). |
| 19 | Does feature selection inside each fold help? | No (differences of about one standard error or less). The apparent advantage of a reduced feature set found in 09 did not survive an honest selection. |
| 20 | Does the production code reproduce the notebooks? | Yes (point forecast to 0.001 £/MWh, metrics to three decimals); no look-ahead (truncation test). |

## 4. The final procedure (D-008, D-009)

For each cutoff, with `ref28` the 28-day same-clock-time median:

```
point = ref28 + L(D) + 0.5 x (Huber shape + GBM shape)
q10   = ref28 + L(D) + quantile-GBM(0.1) deviation, trained net of the in-sample level
q90   = point + 90% quantile of earlier out-of-sample point residuals
```

- **Shape.** Huber regression (spline terms) and a gradient boosting model, each predicting the deviation of price from `ref28` from absolute weather forecasts,
  margin forecasts, calendar variables and price-history terms; their predictions are centred within each day so they carry no daily level.
- **Level `L(D)`.** A Huber regression of the day's mean deviation from `ref28` on the day's mean demand, wind, embedded wind and solar anomalies and weekend and bank-holiday flags.
- **07:00 model.** No demand inputs (demand is mostly unavailable then) and no revision columns.
- **Training.** All labelled days up to D-2; refitted at the start of each 28-day block in the back-tests.

Code: `sip_forecaster/` (`features.py`, `models.py`, `backtest.py`, `__main__.py`); run it as described in the README.

## 5. Results

### Development back-test (17 blocks, `python -m sip_forecaster backtest`)

| | MAE | RMSE | bias | top-8 hit | bottom-8 hit | pinball 10% | pinball 90% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 30.20 | 42.23 | +1.9 | 0.462 | 0.322 | 8.24 | 6.37 |
| model, 09:00 | 27.97 | 37.43 | -0.7 | 0.495 | 0.368 | 5.89 | 6.20 |
| model, 07:00 | 28.35 | 38.14 | -0.7 | 0.483 | 0.356 | 5.97 | 6.22 |

(Point metrics over all 17 blocks; pinball over blocks 1-16, since the 90% offset needs an earlier block, 21,501 rows.) The development numbers are optimistic: the
structure was designed after looking at these same folds (D-008).

### Final hold-out (56 days, scored once, refit at the start of each 28-day block)

The hold-out median price was £134.9, above any development block (£97-118).

| | MAE | RMSE | bias | top-8 hit | bottom-8 hit | pinball 10% | pinball 90% | below q10 | above q90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 48.42 | 62.58 | +0.5 | 0.464 | 0.379 | 11.42 | 10.19 | 12.9% | 20.8% |
| model, 09:00 | 44.15 | 55.44 | -2.1 | 0.471 | 0.395 | 9.45 | 10.48 | 18.6% | 23.7% |
| model, 07:00 | 44.69 | 56.22 | -2.8 | 0.478 | 0.402 | 10.04 | 10.77 | 18.8% | 23.8% |

One fit on development days only (frozen) gives similar results (09:00: MAE 44.07, hit 0.471 / 0.400, pinball 9.22 / 10.62).

What the hold-out supports:

- **Average accuracy improves reliably.** MAE is lower by 4.3 (09:00) and 3.7 (07:00), better on 41 and 38 of 56 days (per-day paired difference -4.26 ± 1.01 and -3.73 ± 0.99), RMSE lower by 7.1 and 6.4. The gain is larger than in development because the baseline is much worse in this higher-priced period.
- **The within-day ranking gain is not established.** The hit-rate differences are +0.007 ± 0.013 (top-8) and +0.016 ± 0.025 (bottom-8) at 09:00, and +0.013 / +0.022 at 07:00, against +0.033 / +0.046 in development. None is distinguishable from zero; in the second block the 09:00 bottom-8 hit rate is slightly below the baseline's. The development estimate was therefore too optimistic, as its caveats said.
- **Quantiles.** The 10% forecast beats the baseline on pinball loss; the 90% forecast does not (10.48 against 10.19). Both intervals are too narrow: 18.6% of prices fall below the 10% forecast and 23.7% above the 90% forecast (nominal 10% each). The upper tail is the weak part.
- **The price level moved within the hold-out.** Mean error is large for model and baseline alike (the model: -12 in the first block, +8 in the second), so the level model follows rising or falling levels only partly.

## 6. Limits and cautions

- 56 hold-out days in two blocks; days are autocorrelated, so the standard errors are optimistic. One higher-priced period is a single regime.
- The hold-out has now been used. Further changes to the model cannot be validated on it, and anything tuned after seeing it would not be an honest out-of-sample result.
- The 10% quantile model is sensitive to small input changes (20): a tiny change in a few anomaly values moved individual 10% forecasts by 2-6 £/MWh on average within a block, while the loss measures over many rows were unchanged. Read single 10% forecasts with that noise in mind.
- Bank holidays are listed by hand for England and Wales through 2026-08-31 and need extending for later dates.
- A look-ahead error in the first version of notebook 05 (first development day only, `level7`/`level28`) affected no model row and is fixed; the production code and notebook 05 now agree.
- Public data only; no outage, interconnector-flow, fuel-price or bid data. The SIP is the outcome of all participants' actions (D-002); competitor behaviour is captured only implicitly.
- The Docker image and compose file are wired to the script but their build has not been tested.

## 7. Possible next steps

- Treat the upper tail directly (quantile calibration that tracks the price level, or a tail-event classifier), since it is the weakest and most valuable part.
- Track the price level better (the mean error moved by about 20 between hold-out blocks).
- Test additional inputs (outages, interconnector flows, fuel prices) and quantile levels other than 10% and 90%.
- Score a longer or later period when more data exist, with the procedure of D-009 frozen.
