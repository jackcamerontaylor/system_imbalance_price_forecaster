"""Command line: python -m sip_forecaster {features,backtest,holdout,forecast} ..."""

import argparse
import sys

import pandas as pd

from .backtest import dev_blocks, holdout_blocks, run_blocks, summarise
from .data import OUT_DIR, TEST_START_DAY, load_tables
from .features import build_features
from .models import fit, predict

FIRST_DAY = pd.Timestamp("2024-10-01")
PRICE_COLS = ["period_start", "day", "cutoff_hour", "ref28", "level", "shape_huber", "shape_gbm", "point", "q10", "q90", "price"]


def get_features(last_day=None):
    tables = load_tables()
    price_last = (tables["imbalance_price"]["period_start"].max().tz_convert("Europe/London").tz_localize(None).normalize())
    last = pd.Timestamp(last_day) if last_day is not None else price_last
    return build_features(tables, pd.date_range(FIRST_DAY, last, freq="D"))


def cmd_features(a):
    F = get_features()
    OUT_DIR.mkdir(exist_ok=True)
    F.to_parquet(OUT_DIR / "features_all.parquet", index=False)
    print("wrote", OUT_DIR / "features_all.parquet", F.shape)


def cmd_backtest(a):
    """Development back-test: 17 blocks of 28 days tiled back from the end of the development period (D-007)."""
    F = get_features(TEST_START_DAY - pd.Timedelta(days=1))              # no hold-out days are touched
    P = run_blocks(F, dev_blocks(F, TEST_START_DAY))
    OUT_DIR.mkdir(exist_ok=True)
    P.to_parquet(OUT_DIR / "backtest_dev.parquet", index=False)
    pd.set_option("display.width", 200)
    print(summarise(P).round(3).to_string())


def cmd_holdout(a):
    """Score the final hold-out (UK days 2026-08-06 .. 2026-09-30) ONCE: refuses to overwrite earlier results."""
    outs = {n: OUT_DIR / f"holdout_{n}.parquet" for n in ("refit", "frozen")}
    if any(p.exists() for p in outs.values()) and not a.force:
        sys.exit("hold-out results already exist; the hold-out is scored once (D-003). Use --force only to reproduce them.")
    hist_path = OUT_DIR / "backtest_dev.parquet"
    if not hist_path.exists():
        sys.exit("run `backtest` first: its out-of-sample residuals feed the 90% quantile offset")
    hist = pd.read_parquet(hist_path)
    F = get_features()
    last = F["day"].max()
    refit = run_blocks(F, holdout_blocks(TEST_START_DAY, last), history=hist)                     # refit at the start of each 28-day block
    frozen = run_blocks(F, [pd.date_range(TEST_START_DAY, last, freq="D")], history=hist)         # one model fitted on development days only
    pd.set_option("display.width", 200)
    for name, P in (("refit", refit), ("frozen", frozen)):
        P.to_parquet(outs[name], index=False)
        print(f"== hold-out, {name} ==")
        print(summarise(P, by_block=(name == "refit")).round(3).to_string())


def cmd_forecast(a):
    """Forecast every half-hour of UK day D as known at the cutoff, training on all labelled days up to D-2."""
    day = pd.Timestamp(a.day)
    F = get_features(day)
    hist_path = OUT_DIR / "backtest_dev.parquet"
    hist = pd.read_parquet(hist_path) if hist_path.exists() else None
    if hist is None:
        print("note: no outputs/backtest_dev.parquet, the 90% quantile is NaN", file=sys.stderr)
    P = run_blocks(F, [pd.date_range(day, day, freq="D")], history=hist, cutoffs=[a.cutoff] if a.cutoff else (7, 9))
    P = P[PRICE_COLS].drop(columns=["price"] if a.drop_price else [])
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"forecast_{day.date()}.parquet"
    P.to_parquet(out, index=False)
    print(P.to_string(index=False) if a.print else f"wrote {out} ({len(P)} rows)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sip_forecaster")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("features", help="build the point-in-time feature table").set_defaults(fn=cmd_features)
    sub.add_parser("backtest", help="development back-test (17 blocks)").set_defaults(fn=cmd_backtest)
    h = sub.add_parser("holdout", help="score the hold-out once")
    h.add_argument("--force", action="store_true")
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
