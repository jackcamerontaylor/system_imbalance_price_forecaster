"""Chronological blocks: refit at the start of each 28-day block on the days available then (last training day D-2 of the
block's first day D, as in production), predict the block, and derive the 90% quantile from earlier out-of-sample residuals."""

import numpy as np
import pandas as pd

from .evaluate import make_folds, pinball, score
from .features import CUTOFF_HOURS
from .models import fit, predict

GAP_DAYS = 2  # last usable day for a block starting on D is D-2


def q90_offset(
    history: pd.DataFrame | None, cutoff: int, block_start: pd.Timestamp, tau: float = 0.9
) -> float:
    """tau-quantile of the point-forecast residuals (price - point) of earlier validation days available at the block start."""
    if history is None or history.empty:
        return np.nan
    h = history[
        (history["cutoff_hour"] == cutoff)
        & (history["day"] <= block_start - pd.Timedelta(days=GAP_DAYS))
    ]
    r = (h["price"] - h["point"]).dropna()
    return float(r.quantile(tau)) if len(r) else np.nan


def run_blocks(
    F: pd.DataFrame, blocks: list, history: pd.DataFrame | None = None, cutoffs=CUTOFF_HOURS
) -> pd.DataFrame:
    """Forecast every block with a model fitted on the days up to block start - 2. `history` holds earlier out-of-sample
    forecasts (columns cutoff_hour, day, price, point) that feed the 90% quantile offset; blocks add to it as they go."""
    outs = []
    for cutoff in cutoffs:
        Fc = F[F["cutoff_hour"] == cutoff]
        hist = (
            history.copy()
            if history is not None
            else pd.DataFrame(columns=["cutoff_hour", "day", "price", "point"])
        )
        for k, val_days in enumerate(blocks):
            start = val_days[0]
            train_days = pd.DatetimeIndex(
                sorted(Fc.loc[Fc["day"] <= start - pd.Timedelta(days=GAP_DAYS), "day"].unique())
            )
            m = fit(Fc, cutoff, train_days)
            out = predict(m, Fc[Fc["day"].isin(val_days)])
            out["q90"] = out["point"] + q90_offset(hist, cutoff, start)
            out["block"] = k
            out["q10_28"], out["q90_28"] = (
                Fc.loc[Fc["day"].isin(val_days), ["q10_28", "q90_28"]].to_numpy().T
            )
            outs.append(out)
            hist = pd.concat(
                [hist, out[["cutoff_hour", "day", "price", "point"]]], ignore_index=True
            )
    return pd.concat(outs, ignore_index=True)


def dev_blocks(
    F: pd.DataFrame, test_start: pd.Timestamp, block: int = 28, n_folds: int = 17
) -> list:
    days = pd.DatetimeIndex(
        sorted(F.loc[(F["day"] < test_start) & F["price"].notna(), "day"].unique())
    )
    return [f["val_days"] for f in make_folds(days, block, n_folds, 1)]


def holdout_blocks(test_start: pd.Timestamp, last_day: pd.Timestamp, block: int = 28) -> list:
    days = pd.date_range(test_start, last_day, freq="D")
    return [days[i : i + block] for i in range(0, len(days), block)]


def summarise(P: pd.DataFrame, by_block: bool = False) -> pd.DataFrame:
    """Metrics of the point forecast, the 28-day-median baseline and the quantile forecasts, per cutoff.

    Point metrics (`n` rows) use every row with a price, a point forecast and ref28. Quantile metrics (`n_q` rows) use
    only rows that also have all four quantiles, so model and baseline are scored on the same rows; in the development
    back-test that excludes block 0, which has no earlier residuals for the 90% offset.
    """
    point_cols = ["price", "point", "ref28"]
    q_cols = ["q10", "q90", "q10_28", "q90_28"]
    rows = {}
    for cutoff, g in P.groupby("cutoff_hour"):
        g = g.dropna(subset=point_cols)
        groups = [("all", g)] + (
            [(f"block {b}", x) for b, x in g.groupby("block")] if by_block else []
        )
        for label, d in groups:
            dq = d.dropna(subset=q_cols)
            for name, pred, q10c, q90c in (
                ("model", "point", "q10", "q90"),
                ("baseline", "ref28", "q10_28", "q90_28"),
            ):
                x = dict(score(d, pred))
                x["n_q"] = len(dq)
                x["pinball10"] = pinball(dq["price"], dq[q10c], 0.1) if len(dq) else np.nan
                x["pinball90"] = pinball(dq["price"], dq[q90c], 0.9) if len(dq) else np.nan
                x["below_q10"] = (dq["price"] < dq[q10c]).mean() if len(dq) else np.nan
                x["above_q90"] = (dq["price"] > dq[q90c]).mean() if len(dq) else np.nan
                rows[(f"{cutoff:02d}:00", label, name)] = x
    return pd.DataFrame(rows).T
