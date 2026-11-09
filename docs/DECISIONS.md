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
