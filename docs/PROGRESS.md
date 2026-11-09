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
- Details in `notebooks/01_data/01_data_audit.ipynb`.
- Next: 02 price EDA (shape, spikes, drift per D-002).

## 2026-11-09 - hold-out set (D-003) and 02 price EDA
- Last 8 weeks held out. 02 now reads development data only; findings in the notebook were updated to match.
- Development-set summary: median £88, 5.5% negative, fat right tail, evening peak and midday negatives,
  level up from about £66-76 (mid/late 2025) to about £113 (Jul 2026), weak own-price persistence
  (corr 0.16 at 1 day). "Same period yesterday" baseline not available at cutoff; use D-2.
- Next: 03 point-in-time features.

## 2026-11-09 - 03 point-in-time features
- `pit_snapshot` in the notebook: latest vintage with `received_at` (else `issued_at`) <= D-1 07:00/09:00 UK per target period; asserted leak-free.
- Coverage at cutoff: wind and embedded ~99.5% at both; demand 20.7% at 07:00, 99.4% at 09:00. 09:00 differs from 07:00 mainly by adding demand.
- Price vs 09:00 features (dev set): demand +0.30, wind -0.22 to -0.25, embedded solar weaker; effects non-linear (steep at the extremes). Elexon and embedded wind correlate 0.94.
- `margin_daily` always published 2-3 days ahead, so safe at both cutoffs; daily corr with mean price about -0.4 (confounded with level drift).
- Next: 04 baselines.

## 2026-11-09 - 04 baselines
- Dev days, 659 days from 2024-10-16. Best baseline: 28-day same-period median, MAE 31.4, RMSE 63.5, bias +1.7, best in every quarter. 7-day median 33.3, global median 34.1, 24 h level 36.0, D-2 same period 41.8 (RMSE 87).
- Longer look-back beats recency (weak persistence). Crude level-shift of the profile did not help. Global median drifts (-20 in 2026Q3).
- Top 1% of prices (> £179) give ~60% of squared error. 28-day profile picks 45% of the day's top-8 and 33% of the bottom-8 periods (random 17%).
- Open: target design to compare in modelling (direct robust loss, deviation from a reference level, quantiles); drop duplicate margin_daily columns when building features.
- Next: feature table + first model on rolling chronological folds (when asked).

## 2026-11-09 - 05 feature table
- Decisions D-004 (three tail metrics, hit rate as headline), D-005 (combined vs split 07/09), D-006 (several model families and targets) logged.
- `notebooks/02_features_and_evaluation/05_feature_table.ipynb` builds `outputs/feature_table_dev.parquet` (git-ignored): 64,702 rows = 32,351 periods x 2 cutoffs, 31 features, targets `price` and `y_dev` (= price - 28-day same-period median). Dev days only.
- Leak checks pass, incl. a deliberately shifted cutoff that is caught, and brute-force re-derivation on random rows.
- 07:00 demand missing for 79% of rows; wind features overlap (0.94-0.997).
- Next: fold definitions, then models and targets (D-005, D-006), scored on tail metrics (D-004).

## 2026-11-09 - 06 folds and metrics
- `notebooks/_eval.py`: `make_folds` (D-007) and `score` (MAE, RMSE, bias, within-day top/bottom-8 hit rate, decile MAE, pinball 10/90). Metrics checked on oracle/reversed/noise/constant cases.
- Reference scores on 17 validation folds (476 days, 09:00): 28-day median MAE 30.2, RMSE 42.2, hit rate 0.46 top-8 / 0.32 bottom-8, pinball 8.16 / 6.29. Not comparable with 04 (different days).
- Fold spread is large (MAE std 6.9, hit std 0.06): compare models paired by fold. Baseline quantiles under-cover (13% / 14% instead of 10%).
- Next: first models (gradient boosting; regularised linear) on these folds, with direct vs deviation targets, combined vs split cutoffs.

## 2026-11-09 - 07 gradient boosting, direct target, 09:00
- sklearn HistGradientBoosting, fixed hyper-parameters, 17 folds, paired against the 28-day median. Feature sets A (calendar+history), B (+forecasts), C (+margin); expanding/sliding; abs vs squared loss. Predictions in `outputs/cv_preds_gbm_direct_0900.parquet` (git-ignored).
- A alone is worse than baseline (MAE +2.5). B/C: MAE -1.4 to -1.6 (+/-0.8), RMSE -3.1 to -3.4 (+/-1.0), top-8 hit +0.03 (+/-0.004, 16/17), bottom-8 +0.04. Margin adds little; squared loss not better; expanding >= sliding.
- Model improves low-price forecasts and ranking, not high prices (bias -4, top-decile MAE worse). Demand dominates importance; most other features ~0.
- Next: deviation target, quantile models, linear model, split vs combined cutoffs, seed/hyper-parameter sensitivity.

## 2026-11-09 - 08 gradient boosting, deviation target, 09:00
- Target `y_dev = price - med28_same`, same folds/model as 07. No improvement over the direct target (B/C expanding MAE within +/-0.3 of direct; sliding worse). Gain over baseline unchanged (MAE -1.5, RMSE -3.1, top-8 hit +0.02, bottom-8 +0.03). Predictions in `outputs/cv_preds_gbm_dev_0900.parquet`.
- Set A (calendar + history) still worse than baseline (MAE +2.1) => model fits noise. Negative bias (-4) persists; may be expected for a conditional-median forecast on a skewed price (unchecked).
- Next: regularisation / seed sensitivity, quantile models, linear model, split vs combined cutoffs.

## 2026-11-09 - 09 regularisation and seed sensitivity
- Grid fixed in advance: 3 leaves x 2 min-leaf x 2 tree counts x 3 feature sets (A, R core 10 features, C full) = 36 configs; direct price, abs loss, expanding, 09:00.
- Gain over baseline is stable: C beats baseline in all 12 settings (MAE -1.6 to -1.9, RMSE -3.4 to -3.8, top-8 hit +0.03, bottom-8 +0.045). A (history only) never beats it (overfits). Seed noise ~0.035 MAE.
- R (core) looks better than C (MAE -2.0 to -2.3) BUT its features were chosen from validation-fold importance (folds 8, 16): optimistic. Fair test needs nested feature selection.
- Bias -4 to -6 for weather models still unexplained (skew vs under-forecast; check share of prices above forecast).
- Next: bias check, quantile models (tails), linear model, split vs combined cutoffs, nested feature selection.

## 2026-11-09 - 10 bias check
- Negative bias is NOT skew (validation mean is 3.8 below median); it is a genuine under-forecast (53.5% of actuals above forecast; median error +3.2), tied to rising price level (fold error vs change in median price: corr 0.65). Fold 16 (median £118): model under-forecasts by 23.8 (baseline 6.8); deviation target does not fix it.
- Gain over baseline is NOT present in the last 4 folds (13-16): dMAE +1.0, RMSE unchanged, hit +0.015/+0.006, versus folds 0-12: dMAE -2.4, RMSE -4.4, hit +0.03/+0.05. Robust to settings and seed, not shown robust to price regime; hold-out is in the high-price regime.
- Next: recency weighting; a model with an explicit level term; better recent-level adjustment of the profile; always report recent folds separately. Then quantile models, linear model, split vs combined cutoffs.

## 2026-11-09 - 11 regularised linear model, 09:00
- Pipeline: spline terms for demand/wind/solar, periodic hour spline, level/profile terms, weekday etc.; ridge (alpha 1/30/300) and Huber (alpha 1/30); direct and deviation targets. Preds in `outputs/cv_preds_linear_0900.parquet`.
- Ridge ~ baseline (squared loss hurt by tail). Huber alpha 30: MAE -1.9, RMSE -4.1, hit +0.035/+0.045 overall (matches/exceeds GBM). Recent folds 13-16: ~no gain in MAE (-0.1/-0.2), RMSE -1.6/-1.8 (GBM: MAE +1.0).
- Level problem unsolved: fold 16 bias -15 to -17 (GBM -24, baseline -6.7). Weather features pull forecasts down while prices stayed high.
- Next: recency weighting; faster-moving reference level; quantile models; split vs combined cutoffs; nested feature selection.

## 2026-11-09 - 12 faster reference level, 09:00
- References: ref28, ref7 (noisy, MAE +1.9), refshift (28-day shape at last-7-day level: MAE +0.28, fixes fold-16 bias of the reference). Huber and GBM on deviation from each. Preds in `outputs/cv_preds_reference_0900.parquet`.
- No gain from a better reference: late-fold (13-16) gain vs ref28 baseline stays ~0 (Huber -0.1 to -0.2; GBM -0.1 to +0.9).
- Under-forecast comes from the learned weather deviation, not the reference: references alone have late bias ~0 to +2; models -12 to -16.
- Next: ablate feature groups (demand, wind, solar, seasonal, margin) with Huber on ref28 to find what drives the negative deviation in recent folds; then recency weighting. Expect little/no hold-out gain if the weather-price relationship shifted.

## 2026-11-09 - 13 feature-group ablation
- Huber on ref28 deviation, one group removed at a time. Late-fold (13-16) negative deviation (-11 predicted vs +0.7 actual) is driven by the `history` group: removing it cuts late bias from -11.8 to -3.7 and gives late MAE -1.2 (full model -0.2), but loses part of the earlier gain (folds 0-12: -2.4 -> -1.1; hit +0.03/+0.05 -> +0.01/+0.02).
- Other groups removed one at a time leave late bias at -10.6 to -12.1. Demand-only is worst (late bias -16.5), wind-only best (+3.2).
- Hypothesis: absolute demand/wind/solar levels carry seasonal info already in the reference; fix = anomaly features (forecast minus its own D-29..D-2 same-period PIT mean) and limited level terms. Diagnostic only: do not select from this table.
- Next: pre-specified anomaly-feature test (all folds + late folds); recency weighting.

## 2026-11-09 - 14 anomaly features, 09:00
- 05 now has 5 anomaly features (forecast minus its D-29..D-2 same-clock-time PIT mean at the same cutoff); leak check (e) added and passing. Table now 36 features.
- Pre-specified variants V0-V3 x Huber/GBM on deviation from ref28. Late-fold bias: Huber -11.8 (V0) -> -2.4 (V3, anomaly only, no level terms); GBM -14.5 -> -4.3. Late MAE vs baseline: -0.24 -> -1.29 (Huber), -0.15 -> -1.17 (GBM); all-fold MAE gain mostly kept (-1.80 / -1.69).
- But the within-day hit-rate gain falls (+0.03/+0.05 -> +0.01/+0.03; paired vs V0 -0.025 +/- 0.006 top-8). Trade-off ranking vs level; no clean winner. Not selecting from these folds alone.
- Open: two-part model (ranking from absolute features, level from anomalies); recency weighting; quantile models; split vs combined cutoffs; nested feature selection. Hold-out still untouched.

## 2026-11-09 - 15 two-part model, 09:00
- Daily level model (mean anomalies -> day's mean deviation from ref28): corr 0.67 out of sample (0.68 late), RMSE 19.2 vs 25.1 with zero; carries the gain. Within-day shape from weather alone adds ~nothing; V0's ranking gain needs history inputs + weather (unexplained).
- Recombination: V0 ordering (centred within day) + anomaly level: Huber MAE -2.06 +/- 0.57 (14/17 folds), RMSE -4.30, hit +0.032/+0.049, late MAE -1.50, late bias -2.2 (V0 -11.8). GBM: MAE -2.03, hit +0.024/+0.033. Best so far on all metrics. D-008 logged as candidate.
- Caveat: designed after seeing dev-fold results (optimistic); late gain on 4 folds; fold-16 bias still -8.4.
- Next: quantile/tail models, 07:00 cutoff (split vs combined, D-005), nested feature selection/seed checks of the new parts, then hold-out once.

## 2026-11-09 - 16 07:00 cutoff, split vs combined
- Same two-part structure (D-008) at 07:00 (no demand) and combined (both cutoffs stacked + indicator), Huber and GBM, same 17 folds; replication of 09:00 results exact. Demand explains almost all of the 07-vs-09 difference (split 07 ~ split 09 without demand).
- 07:00 vs 09:00: Huber MAE +0.51 +/- 0.12 worse, hit -0.022/-0.030 (loses most of its ranking gain); GBM MAE +0.28, hit about equal. 07:00 still beats the baseline (MAE -1.55 Huber, -1.75 GBM; GBM hit +0.018/+0.029). Level model works at 07:00 without demand (late MAE -1.28, late bias -1.6, fold 16 -6.6).
- Combined vs split: no clear difference (MAE -0.09 to +0.14, SE ~0.12) -> D-005 outcome: split. Combined makes the 07:00 and 09:00 forecasts closer (|diff| 4.3-5.4 vs 5.8-6.2).
- Caveats: optimistic SEs (GBM is deterministic, no seed noise); combined Huber median-imputes missing demand; level24h/level_gap differ slightly by cutoff by construction. Preds in `outputs/cv_preds_cutoffs_0700_0900.parquet`.
- Next: quantile/tail models, family choice per cutoff / averaging, nested feature selection/seed checks, then hold-out once.

## 2026-11-09 - 17 quantile forecasts (10%/90%), 07:00 and 09:00
- Variants fixed in advance: baseline empirical quantiles; Q1 quantile GBM on deviation from ref28; Q2 same net of the daily anomaly level; R = two-part point forecast + residual-quantile offsets from earlier validation blocks (all / last 3). Folds 1-16, same rows.
- 10% quantile is predictable: pinball -2.4 +/- 0.4 vs baseline (Q1/Q2, 15 of 16 folds at 09:00), -2.3 at 07:00; R only -1.0 to -1.4. 90% quantile: nothing reliably beats the baseline; Q1/Q2 are worse in the late folds (+0.8 to +1.0); best is R Huber (-0.23 +/- 0.20).
- Calibration: quantile GBMs are too low in the late high-price folds (actual above q90 25-28% of the time, nominal 10%; baseline 15%); R is best calibrated (0.10 below / 0.11 above overall).
- Ranking by q90 (top-8) / q10 (bottom-8) is no better than the point forecast (top-8 -0.014 to -0.020, bottom-8 about 0). Quantiles are an uncertainty product, point forecast stays the ranking.
- Untested idea (not specified in advance): q10 from Q1/Q2 + q90 from R Huber. Caveats: adjacent folds, 4 late folds (GBM deterministic, no seed noise). Preds in `outputs/cv_quantiles_0700_0900.parquet`.
- Next: family choice per cutoff/averaging, seed and nested-selection checks, the q10/q90 combination as a candidate, then hold-out once.

## 2026-11-09 - 18 family choice per cutoff and seeds
- GBM seeds 0-4 give identical predictions (deterministic: no early stopping, no feature sub-sampling); the "single seed" caveats in 16/17 were wrong and are corrected.
- Huber vs GBM per cutoff: weak (09:00 MAE +0.03 +/- 0.16, 07:00 -0.20 +/- 0.12 for GBM minus Huber). Equal-weight blend (shared ref28 and level, average of the two centred shapes) is best or tied: 09:00 MAE -2.23, RMSE -4.46, hit +0.033/+0.046, late MAE -1.80; 07:00 MAE -1.85, RMSE -3.79, hit +0.021/+0.033, late -1.52. Blend vs better family: 0.1-0.3 MAE (1.5-2.5 SE); weights untuned; 5 variants seen on these folds, so optimistic.
- Candidate point forecast: ref28 + L(D) + 0.5 x (Huber shape + GBM shape), split 07:00 (no demand) / 09:00 (demand). Mean level still ~2 low late (fold 16 -6.6 to -8.4). Preds in `outputs/cv_preds_families_0700_0900.parquet`.
- Next: nested feature selection check, the q10/q90 combination, then hold-out once (productionised script first).

## 2026-11-09 - 19 nested feature selection
- GBM within the D-008 structure; selection inside each fold from the training days only (permutation importance on the last 56 training days): N1 = positive importance, N2 = top 10; compared with all features and with the notebook-09 core set R (chosen on validation folds).
- No benefit from nested selection (MAE vs full: 09:00 +0.04 to +0.09, 07:00 -0.07 to -0.08, SE 0.07-0.09; hit rates same or slightly lower). R's earlier edge (-0.35 to -0.43 in 09) disappears in this structure (+0.03 at 09:00, +0.19 at 07:00; worse RMSE, lower 07:00 hit). Decision: keep all V0 inputs.
- Stable top features: demand_mw (09:00), med28_same, emb_wind_mw, emb_solar_mw, wind_mw, hour_frac, mgn_min_demand (07:00); is_weekend and clock_change_day almost never selected.
- Caveats: one inner window, GBM only, level model inputs not selected. Preds in `outputs/cv_preds_selection_0700_0900.parquet`.
- Next: productionised script (frozen point + quantile procedure), then the hold-out scored once.

## 2026-11-09 - production code and parity (20)
- `sip_forecaster/` package (features, models, backtest, CLI: `backtest`, `forecast`, `holdout`, `features`). Docker/compose wired to it (build untested).
- Parity: package reproduces notebook 18 point forecasts (mean |diff| 0.001) and metrics to 3 decimals; q10 matches notebook 17 exactly on identical features but is sensitive to small input changes (after the 2026-01-18 missing-price-period difference, blocks 10-16 differ by 2-6 on average while aggregate pinball is unchanged).
- Found look-ahead error in notebook 05 for day 2024-10-01 only (`level7`, `level28`, first-row slice); no model row affected; fixed in the package. Truncation look-ahead test (24 day/cutoff combinations) passes.
- D-009 logged: final procedure and the hold-out protocol (refit primary, frozen secondary) fixed before scoring. Hold-out not yet run.
- Next: score the hold-out once (`python -m sip_forecaster holdout`), then write-up.

## 2026-11-09 - FINAL HOLD-OUT (UK days 2026-08-06 .. 2026-09-30, 56 days, scored once with the procedure of D-009, committed as d8562c0)
Hold-out median price 134.9 (dev blocks 97-118). Baseline = 28-day same-period median and its empirical 10%/90% quantiles. Refit protocol (primary):

| | MAE | RMSE | bias | top-8 hit | bottom-8 hit | pinball 10% | pinball 90% | below q10 | above q90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 09:00 model | 44.15 | 55.44 | -2.1 | 0.471 | 0.395 | 9.45 | 10.48 | 18.6% | 23.7% |
| 07:00 model | 44.69 | 56.22 | -2.8 | 0.478 | 0.402 | 10.04 | 10.77 | 18.8% | 23.8% |
| baseline | 48.42 | 62.58 | +0.5 | 0.464 | 0.379 | 11.42 | 10.19 | 12.9% | 20.8% |

Frozen (one fit on dev only): 09:00 MAE 44.07, hit 0.471/0.400, pinball 9.22/10.62; 07:00 MAE 44.58, hit 0.471/0.388, pinball 10.01/10.93.
- Point accuracy holds and is larger than in development: MAE -4.3 (09:00) / -3.7 (07:00) vs baseline, better on 41 / 38 of 56 days (per-day paired -4.26 +/- 1.01 and -3.73 +/- 0.99), RMSE -7.1 / -6.4.
- Ranking gain is small and not distinguishable from zero: top-8 +0.007 +/- 0.013, bottom-8 +0.016 +/- 0.025 (09:00; per day), +0.013 / +0.022 at 07:00 (dev: +0.033/+0.046 and +0.021/+0.033). In block 1 (2026-09-03..30) the 09:00 bottom-8 hit is below the baseline (0.406 vs 0.415).
- 10% quantile better than baseline (pinball 9.45 vs 11.42 at 09:00), but 90% quantile worse (10.48 vs 10.19), and both intervals under-cover: actual below q10 18.6%, above q90 23.7% (nominal 10% each; baseline 12.9% / 20.8%). The upper tail again is the weak part; prices were higher and more volatile than in development.
- Per-block bias is large in both model and baseline (block 0: -12; block 1: +8 / +13), i.e. the price level moved within the hold-out; the level model only partly follows it.
- Caveats: 56 days, two blocks; days are autocorrelated so per-day standard errors are optimistic; the procedure was not changed after seeing results.

## 2026-11-09 - write-up and tidy-up
- `docs/REPORT.md` written (task, measurement, what was tried by notebook, final procedure, dev and hold-out results, limits, next steps); README updated.
- Notebook 05 corrected (first-row slice for `level7`/`level28`, 2024-10-01 only; no model row affected) and all notebooks 01-20 re-executed top to bottom in order; package linted (ruff) and the commands re-run.
- State: project complete for the stated scope; nothing pushed.

## 2026-11-09 - review and fixes (D-010)
- **Review findings.**
  - The hold-out and dev numbers in all docs match the saved outputs.
  - The hold-out reproduces bit for bit from commit d8562c0.
  - An independent truncation look-ahead test passes: 4 days, both clock changes, both cutoffs.
  - Notebooks 01-20 ran in order with no errors; ruff is clean.
- **Fixed.**
  - The repeated hour of the autumn clock-change day had no forecast (2025-10-26 in the back-test).
  - The `backtest` printout dropped block 0 from the point metrics, so it disagreed with REPORT.
  - The `forecast` 90% offset ignored hold-out residuals.
  - Bank holidays end at 2026-08-31: extended through 2027, with a warning past the list.
  - The CLAUDE.md working rule was out of date.
  - The `level24h` description now says the window covers 49 periods.
  - Timing assumptions for price publication and embedded `issued_at` are now listed in REPORT limits.
- **Dev back-test re-run.**
  - Rows are now 22,847 per cutoff.
  - 09:00: MAE 27.96, hit 0.494 / 0.368. 07:00: MAE 28.37, hit 0.486 / 0.356.
  - The pre-fix output is kept as `outputs/backtest_dev_d8562c0.parquet`.
- **Hold-out re-run with the fixed code**, in scratch only, to measure the effect.
  - 09:00: MAE 44.22 against 44.15 scored, bias unchanged.
  - Individual forecasts moved by about £1.3/MWh on average from 4 extra training rows, so the shape models are sensitive to training changes.
- Docker tested (27.4):
  - The image builds, and `--help`, `backtest`, `forecast` and `docker compose up` all run.
  - The container back-test matches the local one (point max |diff| 5e-9), and the compose forecast matches too (2e-12).
- Notebooks: see the entry "notebooks re-run with the clock-change fix" below.

## 2026-11-09 - second review: CLI safety fixes and README
- `holdout --force` no longer overwrites the scored hold-out files: it re-runs into `outputs/holdout_*_rerun.parquet` and says the
  current code will not match the scored results (commit d8562c0) exactly.
- `forecast` warns when the inputs for day D are mostly missing (below 90% coverage of `med28_same`, the weather/demand forecasts or
  their anomalies, by cutoff), since the models would otherwise impute silently, and it stops with a message when there is no
  training data (about the first month).
- The `forecast --day 2026-09-30` output is unchanged (max |diff| 4e-12). No change to features, models or results.
- README: "Result in brief" now leads with the headline metric fixed in advance (hit rate, not distinguishable from zero), and
  "What we chose to do, and why" moved above Setup.
- Note: "ruff is clean" in earlier entries means the package; `ruff check .` still flags notebook imports.
- Open (resolved in the next entry): notebooks 01-06 and `outputs/feature_table_dev.parquet` were re-run after 07-20 saved their
  predictions; check that 07-20 still match before relying on them.

## 2026-11-09 - notebooks re-run with the clock-change fix
- **Fix and re-run.**
  - Notebooks 04, 05, 06 and 17 now look up history by clock time only, as the package does (D-010). The brute-force anomaly check in 05
    uses the same rule.
  - All notebooks 01-20 were re-run in order from the repo root, so 07-20 now read the fixed feature table: no errors, all asserts pass.
- **Notebook 20 parity holds again.**
  - Package and notebook-18 point forecasts agree (mean |diff| 0.001), and metrics agree to three decimals (09:00 MAE 27.963).
  - The q10 forecasts are identical in blocks 0-9. In blocks 10-16 they differ by 2-3 on average, from the known 2026-01-18 12:30 difference.
- **Findings updated** in 07-12 and 14-20 to the re-run outputs. 01-06 and 13 needed no change at the precision quoted.
  - Several findings had already disagreed with their own committed output before this run, for example 09's seed std (0.035 against
    0.12) and 10's fold-16 error.
  - Huber results did not move. GBM results moved by about 0.1-0.2 MAE in paired differences.
  - No conclusion changed. The blend is still best or tied (09:00 MAE -2.24, 07:00 -1.83); split beats combined is still not shown either
    way; nested selection still does not help; GBM is still the better single family at 07:00.
  - Small wording changes: at 90% the 07:00 and 09:00 quantile pinball are now about equal (6.43 against 6.44), and R's top-8 loss in 19
    is now about one standard error at both cutoffs.
- **Docs.** REPORT section 3 table (07-09, 18), the parity row and section 6 limits, D-010 and CLAUDE.md updated. The earlier dated
  entries above keep their original numbers.
