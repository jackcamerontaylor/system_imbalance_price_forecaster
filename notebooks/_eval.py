"""Shared evaluation helpers for the modelling notebooks: chronological folds and tail metrics (D-003, D-004)."""

import numpy as np
import pandas as pd


def make_folds(days, block=28, n_folds=17, gap=1, train_window=None):
    """Rolling-origin folds over development days.

    Validation blocks of `block` days tile the END of the development period (so the block closest to
    the hold-out is always complete). The training days for a block are those at least `gap` full days
    before its first day: with gap=1 the last training day is D-2 for the first validation day D, which
    matches production, where the previous day's prices are not yet complete at the run cutoff.
    `train_window=None` gives an expanding window; an integer N keeps only the last N days.
    """
    days = pd.DatetimeIndex(sorted(set(days)))
    folds = []
    for k in range(n_folds):
        hi = len(days) - (n_folds - 1 - k) * block          # exclusive end of this block
        lo = hi - block
        val = days[lo:hi]
        train_end = lo - gap                                  # exclusive index
        train = days[:train_end] if train_window is None else days[max(0, train_end - train_window):train_end]
        folds.append({"fold": k, "train_days": train, "val_days": val})
    return folds


def _hit_rates(day, y, p, k=8, min_periods=40):
    top, bot, n = [], [], 0
    for _, ix in pd.Series(np.arange(len(day))).groupby(day.to_numpy()):
        ix = ix.to_numpy()
        yy, pp = y[ix], p[ix]
        ok = np.isfinite(yy) & np.isfinite(pp)
        yy, pp = yy[ok], pp[ok]
        if len(yy) < min_periods or len(np.unique(pp)) < 5:
            continue
        n += 1
        top.append(len(set(np.argsort(-pp, kind="stable")[:k]) & set(np.argsort(-yy, kind="stable")[:k])) / k)
        bot.append(len(set(np.argsort(pp, kind="stable")[:k]) & set(np.argsort(yy, kind="stable")[:k])) / k)
    return (np.mean(top) if n else np.nan, np.mean(bot) if n else np.nan, n)


def pinball(y, q_pred, q):
    e = y - q_pred
    return np.nanmean(np.maximum(q * e, (q - 1) * e))


def score(d, pred="pred", q10=None, q90=None):
    """Metrics for a frame with columns `day`, `price` and the prediction column(s).

    Point metrics: MAE, RMSE, bias (pred - actual).
    Tail metrics (D-004): within-day top-8/bottom-8 hit rate; MAE on the actual top and bottom decile
    periods of the scored sample (read next to MAE: it can be gamed by extreme forecasts);
    pinball loss at 10% and 90% when quantile columns are given.
    """
    d = d.dropna(subset=["price", pred])
    y, p = d["price"].to_numpy(), d[pred].to_numpy()
    e = p - y
    lo, hi = np.quantile(y, [0.1, 0.9])
    out = {"n": len(d), "MAE": np.abs(e).mean(), "RMSE": np.sqrt((e ** 2).mean()), "bias": e.mean(),
           "MAE_top10": np.abs(e[y >= hi]).mean(), "MAE_bot10": np.abs(e[y <= lo]).mean()}
    out["hit_top8"], out["hit_bot8"], out["hit_days"] = _hit_rates(d["day"], y, p)
    if q10 is not None:
        out["pinball10"] = pinball(d["price"], d[q10], 0.1)
    if q90 is not None:
        out["pinball90"] = pinball(d["price"], d[q90], 0.9)
    return out
