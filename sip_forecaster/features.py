"""Point-in-time feature table, one row per target half-hour and run cutoff (07:00 or 09:00 UK on D-1).

Port of notebook 05. Every value is built from information available at the cutoff:
- forecasts: the latest vintage whose availability (`received_at`, else `issued_at`) is at or before the cutoff;
- price history: prices of days D-2 and earlier, plus (level24h) the 24 h of prices ending one hour before the cutoff;
- margin_daily: publications dated D-2 or earlier.
The target day's own price is attached only as a label (`price`) for training and scoring; no feature reads it.
"""

import numpy as np
import pandas as pd

from .data import BANK_HOLIDAYS, UK_TZ, day_grid, to_uk, uk_day

CUTOFF_HOURS = (7, 9)
ANOM_SRC = {"demand_mw": "demand_anom", "wind_mw": "wind_anom", "emb_wind_mw": "emb_wind_anom",
            "emb_solar_mw": "emb_solar_anom", "wind_total_mw": "wind_total_anom"}
MARGIN_COLS = {"minimum_demand_forecast_mw": "mgn_min_demand", "national_surplus_mw": "mgn_surplus",
               "constrained_plant_mw": "mgn_constrained", "generator_availability_mw": "mgn_gen_avail",
               "max_interconnector_import_mw": "mgn_ic_import"}


def cutoff_utc(day, hour):
    d1 = pd.Timestamp(day) - pd.Timedelta(days=1)
    return (d1 + pd.Timedelta(hours=hour)).tz_localize(UK_TZ, ambiguous=False, nonexistent="shift_forward").tz_convert("UTC")


def _pit_snapshot(df, cut_map, value_cols):
    """Latest vintage per target period available at that period's cutoff."""
    df = df.copy()
    df["avail"] = df["received_at"].fillna(df["issued_at"])
    df["cutoff"] = uk_day(df["period_start"]).map(cut_map)
    ok = df[df["avail"] <= df["cutoff"]].sort_values(["period_start", "avail"]).drop_duplicates("period_start", keep="last")
    ok["age_h"] = (ok["cutoff"] - ok["avail"]).dt.total_seconds() / 3600
    return ok.set_index("period_start")[value_cols + ["avail", "age_h"]]


def build_features(tables: dict[str, pd.DataFrame], days: pd.DatetimeIndex) -> pd.DataFrame:
    """Feature rows for the given contiguous UK days (tz-naive midnights), for both cutoffs.

    `days` should start at least 30 days before the first day of interest, so the anomaly windows are filled.
    """
    days = pd.DatetimeIndex(days)
    grid = day_grid(days)
    loc = to_uk(grid.to_series())
    day_of = loc.dt.tz_localize(None).dt.normalize()
    cut_map = {h: pd.Series({d: cutoff_utc(d, h) for d in days}) for h in CUTOFF_HOURS}

    price_all = tables["imbalance_price"].set_index("period_start")["price_gbp_per_mwh"]
    price = price_all.reindex(grid)                                   # label for the target day (NaN if unknown)

    # --- forecast snapshots on the half-hour grid
    spec = {"demand": ("demand_forecast_elexon", ["demand_mw"]),
            "wind": ("wind_forecast_elexon", ["wind_mw"]),
            "emb": ("wind_solar_forecast_embedded", ["embedded_wind_mw", "embedded_solar_mw"])}
    lo, hi = grid.min() - pd.Timedelta(hours=2), grid.max() + pd.Timedelta(hours=2)
    raw = {t: tables[t][(tables[t]["period_start"] >= lo) & (tables[t]["period_start"] <= hi)] for t, _ in spec.values()}
    snap = {h: {k: _pit_snapshot(raw[t], cut_map[h], c) for k, (t, c) in spec.items()} for h in CUTOFF_HOURS}

    def on_grid(s, floor=False):
        x = s.reindex(grid.floor("h") if floor else grid)
        x.index = grid
        return x

    FB = {}
    for h in CUTOFF_HOURS:
        s = snap[h]
        f = pd.DataFrame(index=grid)
        f["demand_mw"] = on_grid(s["demand"]["demand_mw"])
        f["wind_mw"] = on_grid(s["wind"]["wind_mw"], floor=True)
        f["emb_wind_mw"] = on_grid(s["emb"]["embedded_wind_mw"])
        f["emb_solar_mw"] = on_grid(s["emb"]["embedded_solar_mw"])
        f["wind_total_mw"] = f["wind_mw"] + f["emb_wind_mw"]
        f["demand_age_h"] = on_grid(s["demand"]["age_h"])
        f["wind_age_h"] = on_grid(s["wind"]["age_h"], floor=True)
        f["emb_age_h"] = on_grid(s["emb"]["age_h"])
        avail = pd.concat([on_grid(s["demand"]["avail"]), on_grid(s["wind"]["avail"], floor=True), on_grid(s["emb"]["avail"])], axis=1)
        f["_avail_max"] = avail.max(axis=1)
        FB[h] = f
    for c in ["demand_mw", "wind_mw", "emb_wind_mw", "emb_solar_mw"]:
        FB[9][c.replace("_mw", "") + "_rev"] = FB[9][c] - FB[7][c]
        FB[7][c.replace("_mw", "") + "_rev"] = np.nan

    # --- calendar
    cal = pd.DataFrame(index=grid)
    cal["hour_frac"] = loc.dt.hour + loc.dt.minute / 60
    cal["weekday"] = loc.dt.day_of_week
    cal["is_weekend"] = (cal["weekday"] >= 5).astype(int)
    cal["bank_holiday"] = day_of.isin(BANK_HOLIDAYS).astype(int).to_numpy()
    doy = loc.dt.day_of_year
    cal["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    cal["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    cal["clock_change_day"] = (day_of.map(loc.groupby(day_of).apply(lambda s: s.dt.strftime("%z").nunique())) > 1).astype(int).to_numpy()

    # --- price history (prices of D-2 and earlier; level24h: the 24 h ending 1 h before the cutoff)
    pidx = price_all.index
    pday = uk_day(pidx.to_series())
    df = pd.DataFrame({"price": price_all.to_numpy(), "day": pday.to_numpy(), "hhmm": to_uk(pidx.to_series()).dt.strftime("%H:%M").to_numpy()})
    df["occ"] = df.groupby(["day", "hhmm"]).cumcount()
    wide = df.pivot(index="day", columns=["hhmm", "occ"], values="price")
    wide = wide.reindex(pd.date_range(min(wide.index.min(), days.min()), max(wide.index.max(), days.max()), freq="D"))
    known = wide.shift(2)                                             # row D shows the prices of D-2

    gdf = pd.DataFrame({"day": day_of.to_numpy(), "hhmm": loc.dt.strftime("%H:%M").to_numpy()}, index=grid)
    gdf["occ"] = gdf.groupby(["day", "hhmm"]).cumcount()

    def to_long(Fm):
        ri = Fm.index.get_indexer(gdf["day"])
        ci = Fm.columns.get_indexer(pd.MultiIndex.from_frame(gdf[["hhmm", "occ"]]))
        out = np.full(len(gdf), np.nan)
        ok = (ri >= 0) & (ci >= 0)
        out[ok] = Fm.to_numpy()[ri[ok], ci[ok]]
        return pd.Series(out, index=grid)

    PH = pd.DataFrame(index=grid)
    PH["d2_same"] = to_long(known)
    PH["med7_same"] = to_long(known.rolling(7, min_periods=4).median())
    PH["med28_same"] = to_long(known.rolling(28, min_periods=14).median())
    PH["q10_28"] = to_long(known.rolling(28, min_periods=14).quantile(0.1))      # baseline quantiles (for comparison only)
    PH["q90_28"] = to_long(known.rolling(28, min_periods=14).quantile(0.9))
    vals = wide.to_numpy()

    def flat_median(i, n):
        a, b = max(0, i - 1 - n), max(0, i - 1)                       # rows D-n-1 .. D-2 (empty for the first row)
        v = vals[a:b].ravel()
        return np.nanmedian(v) if np.isfinite(v).sum() >= 24 else np.nan

    wi = {d: i for i, d in enumerate(wide.index)}
    lvl7 = pd.Series({d: flat_median(wi[d], 7) for d in days})
    lvl28 = pd.Series({d: flat_median(wi[d], 28) for d in days})
    PH["level7"] = day_of.map(lvl7).to_numpy()
    PH["level28"] = day_of.map(lvl28).to_numpy()

    pv = price_all
    def level24(hour):
        lv, last = {}, {}
        t = pv.index
        for d in days:
            c = cut_map[hour][d]
            w = pv[(t >= c - pd.Timedelta(hours=25)) & (t <= c - pd.Timedelta(hours=1))]
            lv[d] = w.median() if len(w) >= 24 else np.nan
            last[d] = w.index.max() if len(w) else pd.NaT
        return pd.Series(lv), pd.Series(last)

    L24 = {h: level24(h) for h in CUTOFF_HOURS}

    # --- daily margin features (publications dated D-2 or earlier)
    mg = tables["margin_daily"].copy()
    mg["day"] = pd.to_datetime(mg["day"])
    mg["issued_day"] = uk_day(mg["issued_at"])
    mg = mg[(mg["day"] - mg["issued_day"]).dt.days >= 2].sort_values("issued_day").drop_duplicates("day", keep="last").set_index("day")
    MG = pd.DataFrame({new: day_of.map(mg[old]).to_numpy() for old, new in MARGIN_COLS.items()}, index=grid)
    MG_issued = day_of.map(mg["issued_day"]).to_numpy()

    # --- assemble
    parts = []
    for h in CUTOFF_HOURS:
        t = pd.concat([FB[h], cal, PH, MG], axis=1)
        t["level24h"] = day_of.map(L24[h][0]).to_numpy()
        t["level_gap"] = t["level24h"] - t["level28"]
        t["_level_last"] = day_of.map(L24[h][1]).to_numpy()
        t["_margin_issued"] = MG_issued
        t["cutoff_hour"] = h
        t["day"] = day_of.to_numpy()
        t["cutoff_utc"] = day_of.map(cut_map[h]).to_numpy()
        t["price"] = price
        t["y_dev"] = t["price"] - t["med28_same"]
        parts.append(t)
    T = pd.concat(parts).rename_axis("period_start").reset_index().sort_values(["period_start", "cutoff_hour"]).reset_index(drop=True)

    # --- anomaly features: forecast minus the mean of the same clock time's PIT forecasts over D-29..D-2, same cutoff
    T["_hhmm"] = to_uk(T["period_start"]).dt.strftime("%H:%M")
    T["_occ"] = T.groupby(["cutoff_hour", "day", "_hhmm"]).cumcount()
    for h in CUTOFF_HOURS:
        sub = T[T["cutoff_hour"] == h]
        for src, new in ANOM_SRC.items():
            w = sub.pivot(index="day", columns=["_hhmm", "_occ"], values=src)
            w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="D"))
            typ = w.shift(2).rolling(28, min_periods=14).mean()
            ri = typ.index.get_indexer(sub["day"])
            ci = typ.columns.get_indexer(pd.MultiIndex.from_frame(sub[["_hhmm", "_occ"]]))
            out = np.full(len(sub), np.nan)
            ok = (ri >= 0) & (ci >= 0)
            out[ok] = typ.to_numpy()[ri[ok], ci[ok]]
            T.loc[sub.index, new] = sub[src].to_numpy() - out
    return T
