# Decision log

Append-only. Format: **D-NNN title** - status; decision; why; alternatives; revisit when.

**D-001 Use uv for dependency management** - accepted

**D-002 No competitor / game-theory modelling; watch for market-structure drift** - accepted
The SIP is an outcome of all participants' bids, so a statistical forecaster from public data
captures typical competitor behaviour implicitly; strategic bidding is out of scope. Caveat: GB
battery capacity grew over the two years, so earlier data may reflect a different market (e.g.
wider price spreads) from the latest months. Check for drift in the price EDA; it may affect
train/test splits and warrant weighting recent data or recent-level features.
