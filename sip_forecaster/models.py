"""The forecasting model (D-008, D-009), one instance per run cutoff.

    point = ref28 + L(D) + 0.5 * (centred Huber shape + centred GBM shape)
    q10   = ref28 + L(D) + quantile-GBM(0.1) deviation, trained net of the in-sample level   (notebook 17, Q2)
    q90   = point + offset (see backtest.py: 90% quantile of earlier out-of-sample point residuals)

- ref28: median price of the same clock time over D-29..D-2.
- Shape: Huber regression (splines) and gradient boosting, each on the deviation of price from ref28, with
  absolute weather and price-history inputs; predictions centred within each day so they carry no level.
- Level L(D): Huber regression of the day's mean deviation from ref28 on the day's mean demand/wind/solar anomalies.
- The 07:00 model has no demand inputs (demand is mostly unavailable then) and no revision columns.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

REF = "med28_same"
ABS = ["demand_mw", "wind_mw", "emb_wind_mw", "emb_solar_mw"]
ANOM = ["demand_anom", "wind_anom", "emb_wind_anom", "emb_solar_anom"]
HIST = ["med28_same", "med7_same", "d2_same", "level24h", "level7", "level28", "level_gap"]
MGN = ["mgn_min_demand", "mgn_surplus", "mgn_constrained", "mgn_gen_avail", "mgn_ic_import"]
OTH = ["bank_holiday", "doy_sin", "doy_cos", "clock_change_day"]
GBM_EXTRA = [
    "wind_total_mw",
    "demand_age_h",
    "wind_age_h",
    "emb_age_h",
    "demand_rev",
    "wind_rev",
    "emb_wind_rev",
    "emb_solar_rev",
    "is_weekend",
]
DEMAND_COLS = {"demand_mw", "demand_age_h", "demand_rev", "demand_anom"}
REV_COLS = {"demand_rev", "wind_rev", "emb_wind_rev", "emb_solar_rev"}
DROP = {9: set(), 7: DEMAND_COLS | REV_COLS}
MIN_DAY_ROWS = 40


def gbm_cols(cutoff):
    cols = (
        ["hour_frac", "weekday", "bank_holiday", "doy_sin", "doy_cos", "clock_change_day"]
        + ABS
        + MGN
        + GBM_EXTRA
        + HIST
    )
    return [c for c in dict.fromkeys(cols) if c not in DROP[cutoff]]


def level_cols(cutoff):
    return [a for a in ANOM if a not in DROP[cutoff]] + ["is_weekend", "bank_holiday"]


def _huber(cutoff):
    weather = [c for c in ABS if c not in DROP[cutoff]]
    lin = HIST + MGN + OTH
    parts = []
    if weather:
        parts.append(
            (
                "spl",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    SplineTransformer(n_knots=6, degree=3, extrapolation="linear"),
                    StandardScaler(),
                ),
                weather,
            )
        )
    parts += [
        (
            "hour",
            SplineTransformer(
                knots=np.linspace(0, 24, 13).reshape(-1, 1), degree=3, extrapolation="periodic"
            ),
            ["hour_frac"],
        ),
        ("lin", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), lin),
        ("wd", OneHotEncoder(handle_unknown="ignore"), ["weekday"]),
    ]
    cols = weather + ["hour_frac"] + lin + ["weekday"]
    return Pipeline(
        [
            ("pre", ColumnTransformer(parts)),
            ("est", HuberRegressor(alpha=30, epsilon=1.35, max_iter=300)),
        ]
    ), cols


def _gbm(loss="absolute_error", quantile=None):
    kw = {"quantile": quantile} if quantile is not None else {}
    return HistGradientBoostingRegressor(
        loss=loss,
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=100,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=0,
        **kw,
    )


def _level_model():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        HuberRegressor(alpha=10, epsilon=1.35, max_iter=300),
    )


def daily_table(F: pd.DataFrame) -> pd.DataFrame:
    """One row per day: mean anomalies and calendar flags (inputs of the level model), and the day's mean
    deviation of the price from ref28 (target; only days with at least 40 valid periods, NaN otherwise)."""
    g = F.groupby("day")
    d = g[ANOM].mean()
    d["is_weekend"] = g["is_weekend"].mean()
    d["bank_holiday"] = g["bank_holiday"].mean()
    ok = F["price"].notna() & F[REF].notna()
    dev = (F["price"] - F[REF]).where(ok)
    agg = dev.groupby(F["day"]).agg(["mean", "count"])
    d["target"] = agg["mean"].where(agg["count"] >= MIN_DAY_ROWS).reindex(d.index)
    return d


@dataclass
class Fitted:
    cutoff: int
    huber: Pipeline
    huber_cols: list
    gbm: HistGradientBoostingRegressor
    gbm_cols: list
    q10: HistGradientBoostingRegressor
    level: Pipeline
    level_cols: list


def fit(F: pd.DataFrame, cutoff: int, train_days) -> Fitted:
    """Fit all parts on the rows of `F` (one cutoff) whose day is in `train_days` and that have a price and ref28."""
    F = F[F["day"].isin(train_days)]
    tr = F[F["price"].notna() & F[REF].notna()]
    ydev = tr["price"] - tr[REF]
    lc, gc = level_cols(cutoff), gbm_cols(cutoff)
    hub, hc = _huber(cutoff)
    hub.fit(tr[hc], ydev)
    gbm = _gbm().fit(tr[gc], ydev)
    dtr = daily_table(F)
    fitd = dtr[dtr["target"].notna()]
    lm = _level_model().fit(fitd[lc], fitd["target"])
    lt_train = pd.Series(
        lm.predict(dtr[lc]), index=dtr.index
    )  # in-sample fitted level, all training days
    q10 = _gbm("quantile", 0.1).fit(tr[gc], ydev - tr["day"].map(lt_train).fillna(0.0))
    return Fitted(cutoff, hub, hc, gbm, gc, q10, lm, lc)


def predict(m: Fitted, F: pd.DataFrame) -> pd.DataFrame:
    """Point forecast and 10% quantile for the rows of `F` (one cutoff; all rows of each day present)."""
    F = F.reset_index(drop=True)
    d = daily_table(F)
    lvl = F["day"].map(pd.Series(m.level.predict(d[m.level_cols]), index=d.index))
    out = F[["period_start", "day", "cutoff_hour", REF, "price"]].rename(columns={REF: "ref28"})
    centre = lambda s: s - s.groupby(F["day"]).transform("mean")
    out["level"] = lvl
    out["shape_huber"] = centre(pd.Series(m.huber.predict(F[m.huber_cols]), index=F.index))
    out["shape_gbm"] = centre(pd.Series(m.gbm.predict(F[m.gbm_cols]), index=F.index))
    out["point"] = out["ref28"] + out["level"] + 0.5 * (out["shape_huber"] + out["shape_gbm"])
    out["q10"] = out["ref28"] + out["level"] + m.q10.predict(F[m.gbm_cols])
    return out
