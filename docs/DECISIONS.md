# Decision log

Append-only. Format: **D-NNN title** - status; decision; why; alternatives; revisit when.

**D-001 Use uv for dependency management** - accepted

**D-002 No competitor / game-theory modelling; watch for market-structure drift** - accepted
The SIP is an outcome of all participants' bids, so a statistical forecaster from public data
captures typical competitor behaviour implicitly; strategic bidding is out of scope. Caveat: GB
battery capacity grew over the two years, so earlier data may reflect a different market (e.g.
wider price spreads) from the latest months. Check for drift in the price EDA; it may affect
train/test splits and warrant weighting recent data or recent-level features.

**D-003 Chronological hold-out: last 8 weeks** - accepted
Test set = UK days 2026-08-06 to 2026-09-30 (`TEST_START` in `notebooks/_common.py`). Exploration and
model selection use only earlier days (`dev_only()`), with rolling chronological folds inside that
set; no random splits. The test set is scored once, at the end. For the final submission the model
is refit on all data.

**D-004 Tail-focused metrics** - accepted
The value of the forecast is in the extremes (cheap and expensive half-hours), so the headline metric
is tail-focused, with MAE, RMSE and bias reported alongside. Three tail measures, all reported:
(1) within-day top-8/bottom-8 hit rate (headline, closest to the charge/discharge decision),
(2) pinball loss at the 10% and 90% quantiles, (3) MAE restricted to actual top and bottom deciles
(always read next to overall MAE, since it can be gamed by extreme forecasts).
Baseline to beat: 28-day same-period median (04).

**D-005 Compare combined and split 07:00/09:00 models** - accepted
Fit both a single model with a cutoff-hour feature and separate 07:00 and 09:00 models, on the same
folds, and compare on the tail metric. At 07:00 demand is mostly missing (20.7% coverage).

**D-006 Compare several model families and target designs** - accepted
Several model kinds (e.g. gradient boosting, regularised linear/splines) and targets (direct price,
deviation from the 28-day profile, quantiles). One shared feature table so all variants see identical
inputs; scored on identical chronological folds inside the development set (D-003).

**D-007 Fold design** - accepted
17 validation blocks of 28 days tiled backwards from the end of the development period (2025-04-17 to
2026-08-05). Training ends 1 full day before each block (latest usable day D-2, as in production); the model
is fixed across the block. Expanding and 180-day sliding training windows are both compared. Models are
compared with the baseline fold by fold (paired), because fold-to-fold spread in MAE (std ~7) is large.
Code: `notebooks/_eval.py`.

**D-008 Two-part structure: daily level from anomaly features, within-day ordering from absolute features** - proposed (candidate, not final)
`forecast = ref28 + L(D) + centred within-day deviation of a model on absolute weather + history inputs`.
Level L(D): Huber regression (alpha 10) of the day's mean deviation from the 28-day same-period median on the
day's mean demand/wind/solar anomalies (forecast minus its own D-29..D-2 same-clock-time point-in-time mean)
and weekend/bank-holiday flags. Why: absolute weather and level inputs produced a large under-forecast in the
recent high-price folds (notebooks 10-13) while anomaly inputs fixed the level but lost the ranking gain
(14); separating the two keeps both (15). Caveat: designed after seeing results on the development folds,
so the hold-out is the first unbiased test. Revisit if quantile models or the 07:00 cutoff need a different structure.

**D-005 outcome (notebook 16): split 07:00 and 09:00 models** - proposed from dev folds (not final)
Stacking both cutoffs with a cutoff indicator did not beat separate models (MAE within +/-0.15, standard error ~0.12;
no consistent late-fold or hit-rate gain), so separate models are used (simpler, same score). The 09:00 model keeps the
demand inputs; the 07:00 model drops them (demand is missing for ~79% of rows, all outside the early hours), plus the
`*_rev` columns. The 07:00 level model uses wind/embedded wind/solar anomalies only. Most of the 07-vs-09 difference is the demand
forecast: it matters for the ranking gain with Huber. Family may differ by cutoff (GBM at 07:00, Huber at 09:00); unconfirmed.

**D-009 Final procedure and hold-out protocol (declared before the hold-out is scored)** - accepted
Procedure, per cutoff (07:00 without demand inputs, 09:00 with): `point = ref28 + L(D) + 0.5 x (Huber shape + GBM shape)`;
`q10 = ref28 + L(D) + quantile-GBM(0.1)` trained net of the in-sample level (Q2, notebook 17); `q90 = point + 90% quantile of
earlier out-of-sample point residuals` (offsets from all earlier validation blocks, last usable day D-2). All V0 inputs, no feature
selection (notebook 19). Code: `sip_forecaster/` (parity with the notebooks in notebook 20).
Hold-out (UK days 2026-08-06 .. 2026-09-30, 56 days), scored once, two protocols both fixed in advance: **refit** (primary; two 28-day
blocks as in D-007, models refitted at each block start on days up to block start - 2, so block 2 uses block-1 labels, q90 offsets from
the 17 dev blocks plus earlier hold-out blocks) and **frozen** (one fit on development days only). Metrics as D-004 (headline: top-8/bottom-8
hit rate), against the 28-day median and its empirical quantiles. No change to the procedure after seeing the results; results are reported
as they come out. The q10-from-Q2 / q90-from-offset combination was not pre-specified in the development phase (notebook 17), so the
hold-out is its first clean test.
