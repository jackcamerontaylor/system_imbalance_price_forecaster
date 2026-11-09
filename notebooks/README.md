# Notebooks

Grouped by stage; run in numerical order. **Run them with the repository root as the working directory**
(they read `candidate_data/` and `outputs/` by relative path, and add `notebooks/` to the import path for the shared
helpers). Notebook 05 builds `outputs/feature_table_dev.parquet`, which all later ones read; 17-20 also read forecasts
saved by earlier notebooks. Findings are at the end of each notebook; the summary is in [`docs/REPORT.md`](../docs/REPORT.md).

`_common.py` (data loading, UK-time helpers) and `_eval.py` (folds and metrics) are shared helpers.

| Folder | Notebooks |
| --- | --- |
| `01_data/` | 01 data audit · 02 price exploration (development set) · 03 point-in-time (vintage) features · 04 baseline references |
| `02_features_and_evaluation/` | 05 feature table (both cutoffs) · 06 folds and metrics |
| `03_model_search/` | 07-09 gradient boosting (direct price, deviation target, regularisation) · 10-13 under-forecasting when prices rise (bias, linear models, reference level, feature-group ablation) · 14 anomaly features · 15 two-part model (daily level + within-day shape) |
| `04_final_model/` | 16 07:00 against 09:00 cutoff · 17 quantile forecasts · 18 model family and blend · 19 nested feature selection |
| `05_production_check/` | 20 production code: parity with the notebooks and look-ahead test |
