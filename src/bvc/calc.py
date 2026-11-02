"""Core variance calculations. Pure pandas, no I/O, so every function is unit-tested on small frames.

Convention: variance = actual (Ist) - plan (Soll).
For expenses a negative variance is an under-spend; for income a negative variance is a shortfall.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_variance(df: pd.DataFrame, plan: str = "soll", actual: str = "ist") -> pd.DataFrame:
    """Add `variance` (Ist - Soll) and `variance_pct` (relative to Soll, NaN where Soll is 0)."""
    out = df.copy()
    out["variance"] = out[actual] - out[plan]
    out["variance_pct"] = np.where(out[plan] != 0, out["variance"] / out[plan].where(out[plan] != 0), np.nan)
    return out


def underspent(df: pd.DataFrame, threshold: float = 0.10) -> pd.DataFrame:
    """Rows whose actual is more than `threshold` below plan (expenses view)."""
    return df[df["variance_pct"] < -threshold].sort_values("variance")


def overspent(df: pd.DataFrame, threshold: float = 0.10) -> pd.DataFrame:
    return df[df["variance_pct"] > threshold].sort_values("variance", ascending=False)


def decompose(df: pd.DataFrame, by: str, plan: str = "soll", actual: str = "ist") -> pd.DataFrame:
    """Split the total variance by a dimension. Contributions always add up to the total variance."""
    g = df.groupby(by, as_index=False)[[plan, actual]].sum()
    g["variance"] = g[actual] - g[plan]
    total = g["variance"].sum()
    g["share_of_total_variance"] = g["variance"] / total if total != 0 else np.nan
    return g.sort_values("variance", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def concentration(df: pd.DataFrame, n: int, col: str = "variance") -> float:
    """Share of the gross (absolute) deviation that the `n` largest lines explain."""
    a = df[col].abs().sort_values(ascending=False)
    return float(a.head(n).sum() / a.sum()) if a.sum() else float("nan")


def bridge(df: pd.DataFrame, label: str, top_n: int = 8, plan: str = "soll", actual: str = "ist") -> pd.DataFrame:
    """Variance bridge (waterfall) from total plan to total actual.

    The `top_n` largest absolute deviations get their own step, the rest are grouped into one
    "Other" step so the bridge still closes exactly: plan + sum(steps) = actual.
    Columns: step, kind (total|delta), value, start, end.
    """
    d = df[[label, plan, actual]].copy()
    d["variance"] = d[actual] - d[plan]
    d = d.sort_values("variance", key=lambda s: s.abs(), ascending=False)
    head, tail = d.head(top_n), d.iloc[top_n:]
    steps = [(r[label], r["variance"]) for _, r in head.iterrows()]
    if len(tail):
        steps.append((f"Other ({len(tail)})", float(tail["variance"].sum())))
    rows = [{"step": "Plan (Soll)", "kind": "total", "value": float(d[plan].sum()), "start": 0.0,
             "end": float(d[plan].sum())}]
    level = float(d[plan].sum())
    for name, v in steps:
        rows.append({"step": name, "kind": "delta", "value": float(v), "start": level, "end": level + float(v)})
        level += float(v)
    rows.append({"step": "Actual (Ist)", "kind": "total", "value": float(d[actual].sum()), "start": 0.0,
                 "end": float(d[actual].sum())})
    return pd.DataFrame(rows)
