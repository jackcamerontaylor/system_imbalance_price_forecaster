"""Command line: python -m sip_forecaster {features,backtest,holdout,forecast} ..."""

import argparse
import sys

import pandas as pd

from .backtest import dev_blocks, holdout_blocks, run_blocks, summarise
from .data import BANK_HOLIDAYS_END, OUT_DIR, TEST_START_DAY, load_tables
from .features import CUTOFF_HOURS, build_features
from .models import ANOM, DROP, REF

FIRST_DAY = pd.Timestamp("2024-10-01")
# Inputs checked by `forecast` for day D (minus those a cutoff's model does not use, models.DROP): the reference
# profile, the weather/demand forecasts and their anomalies (empty in the first ~30 days of data).
REQUIRED_INPUTS = [REF, "demand_mw", "wind_mw", "emb_wind_mw", "emb_solar_mw", *ANOM]
HIST_COLS = ["cutoff_hour", "day", "price", "point"]
PRICE_COLS = [
    "period_start",
    "day",
    "cutoff_hour",
    "ref28",
    "level",
    "shape_huber",
    "shape_gbm",
    "point",
    "q10",
    "q90",
    "price",
]


def warn_missing_inputs(F, day, cutoffs, min_cover=0.9):
    """Warn when the inputs for day D at a cutoff are mostly missing. The models would still produce a forecast (Huber
    median-imputes, the GBM handles NaN), so without this check missing data would pass silently."""
    for h in cutoffs:
        g = F[(F["day"] == day) & (F["cutoff_hour"] == h)]
        cols = [c for c in REQUIRED_INPUTS if c not in DROP[h]]
        if g.empty:
            print(f"warning: no feature rows for {day.date()} at {h:02d}:00", file=sys.stderr)
            continue
        cover = g[cols].notna().mean()
        low = cover[cover < min_cover]
        if len(low):
            detail = ", ".join(f"{c} {v:.0%}" for c, v in low.items())
            print(
                f"warning: {day.date()} {h:02d}:00 inputs mostly missing ({detail}); the forecast "
                "relies on imputed values or is NaN",
                file=sys.stderr,
            )


def get_features(last_day=None):
    tables = load_tables()
    price_last = (
        tables["imbalance_price"]["period_start"]
        .max()
        .tz_convert("Europe/London")
        .tz_localize(None)
        .normalize()
    )
    last = pd.Timestamp(last_day) if last_day is not None else price_last
    return build_features(tables, pd.date_range(FIRST_DAY, last, freq="D"))


def cmd_features(a):
    F = get_features()
    OUT_DIR.mkdir(exist_ok=True)
    F.to_parquet(OUT_DIR / "features_all.parquet", index=False)
    print("wrote", OUT_DIR / "features_all.parquet", F.shape)


def cmd_backtest(a):
    """Development back-test: 17 blocks of 28 days tiled back from the end of the development period (D-007)."""
    F = get_features(TEST_START_DAY - pd.Timedelta(days=1))  # no hold-out days are touched
    P = run_blocks(F, dev_blocks(F, TEST_START_DAY))
    OUT_DIR.mkdir(exist_ok=True)
    P.to_parquet(OUT_DIR / "backtest_dev.parquet", index=False)
    pd.set_option("display.width", 200)
    print(summarise(P).round(3).to_string())


def cmd_holdout(a):
    """Score the final hold-out (UK days 2026-08-06 .. 2026-09-30) ONCE: never overwrites the scored results.

    With --force the hold-out is re-run into separate `holdout_*_rerun.parquet` files. The scored results came from commit
    d8562c0; the current code differs (clock-change fix, D-010), so a re-run does not reproduce them exactly.
    """
    outs = {n: OUT_DIR / f"holdout_{n}.parquet" for n in ("refit", "frozen")}
    if any(p.exists() for p in outs.values()):
        if not a.force:
            sys.exit(
                "hold-out results already exist; the hold-out is scored once (D-003). "
                "--force re-runs it into holdout_*_rerun.parquet without touching the scored files."
            )
        outs = {n: OUT_DIR / f"holdout_{n}_rerun.parquet" for n in outs}
        print(
            "note: re-run with the current code; the scored results (commit d8562c0) are left unchanged "
            "and this re-run will not match them exactly (REPORT section 6)",
            file=sys.stderr,
        )
    hist_path = OUT_DIR / "backtest_dev.parquet"
    if not hist_path.exists():
        sys.exit("run `backtest` first: its out-of-sample residuals feed the 90% quantile offset")
    hist = pd.read_parquet(hist_path)
    F = get_features()
    last = F["day"].max()
    refit = run_blocks(
        F, holdout_blocks(TEST_START_DAY, last), history=hist
    )  # refit at the start of each 28-day block
    frozen = run_blocks(
        F, [pd.date_range(TEST_START_DAY, last, freq="D")], history=hist
    )  # one model fitted on development days only
    pd.set_option("display.width", 200)
    for name, P in (("refit", refit), ("frozen", frozen)):
        P.to_parquet(outs[name], index=False)
        print(f"== hold-out, {name} ==")
        print(summarise(P, by_block=(name == "refit")).round(3).to_string())


def cmd_forecast(a):
    """Forecast every half-hour of UK day D as known at the cutoff, training on all labelled days up to D-2."""
    day = pd.Timestamp(a.day)
    if day > BANK_HOLIDAYS_END:
        print(
            f"warning: bank holidays are listed only to {BANK_HOLIDAYS_END.date()} (sip_forecaster/data.py)",
            file=sys.stderr,
        )
    F = get_features(day)
    cutoffs = [a.cutoff] if a.cutoff else list(CUTOFF_HOURS)
    warn_missing_inputs(F, day, cutoffs)
    labelled = F["price"].notna() & F[REF].notna() & (F["day"] <= day - pd.Timedelta(days=2))
    if not labelled.any():
        sys.exit(
            f"no training data for {day.date()}: the model needs labelled days with a 28-day reference before D-2 "
            f"(about a month after the first data day, {FIRST_DAY.date()})"
        )
    # Out-of-sample residuals for the 90% offset: the development back-test plus, when present, the refit hold-out
    # (as in the hold-out protocol, D-009). q90_offset keeps only days up to D-2.
    paths = [OUT_DIR / "backtest_dev.parquet", OUT_DIR / "holdout_refit.parquet"]
    parts = [pd.read_parquet(p, columns=HIST_COLS) for p in paths if p.exists()]
    hist = pd.concat(parts, ignore_index=True) if parts else None
    if not (OUT_DIR / "backtest_dev.parquet").exists():
        print("note: no outputs/backtest_dev.parquet; run `backtest` first", file=sys.stderr)
    if hist is None:
        print("note: no out-of-sample residuals, the 90% quantile is NaN", file=sys.stderr)
    P = run_blocks(
        F,
        [pd.date_range(day, day, freq="D")],
        history=hist,
        cutoffs=cutoffs,
    )
    P = P[PRICE_COLS].drop(columns=["price"] if a.drop_price else [])
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"forecast_{day.date()}.parquet"
    P.to_parquet(out, index=False)
    print(P.to_string(index=False) if a.print else f"wrote {out} ({len(P)} rows)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sip_forecaster")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("features", help="build the point-in-time feature table").set_defaults(
        fn=cmd_features
    )
    sub.add_parser("backtest", help="development back-test (17 blocks)").set_defaults(
        fn=cmd_backtest
    )
    h = sub.add_parser("holdout", help="score the hold-out once")
    h.add_argument(
        "--force",
        action="store_true",
        help="re-run into holdout_*_rerun.parquet; the scored results are never overwritten",
    )
    h.set_defaults(fn=cmd_holdout)
    f = sub.add_parser("forecast", help="forecast one UK day at the 07:00 and 09:00 cutoffs")
    f.add_argument("--day", required=True, help="UK day D, YYYY-MM-DD")
    f.add_argument("--cutoff", type=int, choices=(7, 9), help="default: both")
    f.add_argument("--print", action="store_true")
    f.add_argument("--drop-price", action="store_true", help="omit the realised price column")
    f.set_defaults(fn=cmd_forecast)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
