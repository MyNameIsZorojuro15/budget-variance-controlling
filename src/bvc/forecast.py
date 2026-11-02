"""Rolling forecast of year-end actuals (Ist) per ministry, with a backtest.

The source publishes annual figures only (no monthly execution), so the forecast works at the
start of each budget year: given that year's plan (Soll) and the execution history of the years
before it, how much will actually be spent? It is evaluated with a rolling origin: for each test
year only data from earlier years is used for the execution history.

Methods
  plan          Ist = Soll                               (the budget taken at face value)
  last_actual   Ist = Ist of the previous year            (naive)
  ratio_mean_k  Ist = Soll x mean(Ist/Soll, last k years)
  ratio_median_k Ist = Soll x median(Ist/Soll, last k years)
  ratio_shrunk_k Ist = Soll x (1 + 0.5 x (mean ratio - 1)): adjust only half-way towards history
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SHRINKAGE = 0.5
METHODS = ("plan", "last_actual", "ratio_mean_3", "ratio_median_3", "ratio_mean_5", "ratio_shrunk_3")


def forecast_year(hist: pd.DataFrame, year: int, method: str, soll_year: pd.Series | None = None) -> pd.Series:
    """Forecast Ist for `year` per ministry (index ep_id).

    `hist` has columns ep_id, year, soll, ist. Only rows with year < `year` provide actuals;
    the plan of `year` is taken from `soll_year` (or from `hist` when it contains that year).
    """
    past = hist[hist["year"] < year]
    if soll_year is None:
        soll_year = hist[hist["year"] == year].set_index("ep_id")["soll"]
    soll_year = soll_year[soll_year > 0]
    if method == "plan":
        return soll_year.rename("forecast")
    if method == "last_actual":
        last = past[past["year"] == year - 1].set_index("ep_id")["ist"]
        return last.reindex(soll_year.index).dropna().rename("forecast")
    kind, _, k = method.rpartition("_")
    k = int(k)
    p = past[past["soll"] > 0].copy()
    p["ratio"] = p["ist"] / p["soll"]
    p = p[p["year"] >= year - k]
    fn = {"ratio_mean": "mean", "ratio_median": "median", "ratio_shrunk": "mean"}[kind]
    ratio = p.groupby("ep_id")["ratio"].agg(fn)
    if kind == "ratio_shrunk":
        ratio = 1 + SHRINKAGE * (ratio - 1)
    return (soll_year * ratio.reindex(soll_year.index)).dropna().rename("forecast")


def wape(forecast: pd.Series, actual: pd.Series) -> float:
    """Weighted absolute percentage error: sum|F-A| / sum A."""
    return float((forecast - actual).abs().sum() / actual.sum())


def backtest(hist: pd.DataFrame, methods=METHODS, first_test_year: int | None = None,
             min_history: int = 3) -> pd.DataFrame:
    """Rolling-origin backtest. One row per (test year, method) with the error at ministry and total level.

    Every method is scored on the same ministries each year (those every method can forecast).
    """
    years = sorted(hist["year"].unique())
    first = first_test_year if first_test_year is not None else years[0] + min_history
    rows = []
    for y in [t for t in years if t >= first]:
        actual = hist[hist["year"] == y].set_index("ep_id")["ist"]
        fcs = {m: forecast_year(hist, y, m) for m in methods}
        common = set(actual.index)
        for f in fcs.values():
            common &= set(f.index)
        idx = sorted(common)
        a = actual.loc[idx]
        for m, f in fcs.items():
            f = f.loc[idx]
            rows.append({"year": y, "method": m, "ministries": len(idx), "actual": float(a.sum()),
                         "forecast": float(f.sum()), "wape": wape(f, a),
                         "total_error_pct": float((f.sum() - a.sum()) / a.sum())})
    return pd.DataFrame(rows)


def summarise(bt: pd.DataFrame, exclude_years=()) -> pd.DataFrame:
    """Average error per method over the test years (optionally excluding crisis years)."""
    b = bt[~bt["year"].isin(exclude_years)]
    return (b.groupby("method")
              .agg(years=("year", "nunique"), mean_wape=("wape", "mean"),
                   mean_abs_total_error=("total_error_pct", lambda s: float(s.abs().mean())),
                   mean_total_bias=("total_error_pct", "mean"))
              .sort_values("mean_wape").reset_index())
