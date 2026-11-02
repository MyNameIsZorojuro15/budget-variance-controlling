"""Three charts for reports/: variance bridge, execution heat map, forecast backtest."""
from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BELOW = "#2b6a99"   # below plan (under-spend)
ABOVE = "#d9822b"   # above plan (over-spend)
TOTAL = "#5b6770"
GRID = "#d8dde1"
INK = "#1f2933"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False})


def _waterfall(ax, steps: pd.DataFrame, title: str, wrap: int = 14) -> None:
    """Waterfall in EUR bn. The value axis is truncated (totals are ~500 bn, steps are a few bn)."""
    s = steps.copy()
    for c in ("value", "start", "end"):
        s[c] = s[c] / 1e9
    lo = min(s["start"][s["kind"] == "delta"].min(), s["end"].min()) if (s["kind"] == "delta").any() else s["end"].min()
    hi = max(s["start"].max(), s["end"].max())
    floor = np.floor((lo - 0.25 * (hi - lo) - 1) / 5) * 5
    x = np.arange(len(s))
    for i, r in s.iterrows():
        if r["kind"] == "total":
            ax.bar(i, r["end"] - floor, bottom=floor, color=TOTAL, width=0.62)
            ax.text(i, r["end"] + 0.02 * (hi - floor), f"{r['end']:,.1f}", ha="center", va="bottom", fontsize=8.5,
                    fontweight="bold")
        else:
            bottom = min(r["start"], r["end"])
            ax.bar(i, abs(r["value"]), bottom=bottom, color=ABOVE if r["value"] > 0 else BELOW, width=0.62)
            ax.text(i, max(r["start"], r["end"]) + 0.02 * (hi - floor), f"{r['value']:+.1f}", ha="center",
                    va="bottom", fontsize=8.5)
        if i < len(s) - 1:
            ax.plot([i + 0.31, i + 0.69], [r["end"]] * 2, color=GRID, lw=1)
    ax.set_ylim(floor, hi + 0.12 * (hi - floor))
    ax.set_xticks(x)
    ax.set_xticklabels([fill(t, wrap, break_long_words=False) for t in s["step"]], fontsize=7.5)
    ax.set_ylabel("EUR bn (axis starts at %d)" % floor)
    ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def variance_bridge(bridge_ministry: pd.DataFrame, bridge_bucket: pd.DataFrame, year: int, out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
    _waterfall(axes[0], bridge_ministry, f"{year}: by ministry (Einzelplan), plan to actual", wrap=15)
    _waterfall(axes[1], bridge_bucket, f"{year}: by driver, plan to actual", wrap=11)
    fig.suptitle(f"Federal expenses {year}: variance bridge from plan (Soll) to actual (Ist)", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.text(0.01, 0.005, "Blue = below plan, orange = above plan. Source: bundeshaushalt.de (BMF), own calculation.",
             fontsize=8, color=TOTAL)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def execution_heatmap(heat: pd.DataFrame, year: int, out: Path) -> Path:
    h = heat.copy()
    h["name"] = h["ep_label"]
    years = [c for c in h.columns if isinstance(c, (int, np.integer))]
    h = h.sort_values(year)
    data = h[years].to_numpy(dtype=float) * 100
    fig, ax = plt.subplots(figsize=(11.5, 0.46 * len(h) + 1.9))
    im = ax.imshow(np.clip(data, -25, 25), cmap="RdBu_r", vmin=-25, vmax=25, aspect="auto")
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    ax.set_yticks(range(len(h)))
    ax.set_yticklabels(h["ep_id"] + "  " + h["name"], fontsize=8.5)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isnan(data[i, j]):
                continue
            v = data[i, j]
            ax.text(j, i, (f"{v:+.0f}" if abs(v) >= 0.5 else "0"), ha="center", va="center", fontsize=7.5,
                    color="white" if abs(np.clip(v, -25, 25)) > 15 else INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f"Actual vs plan by ministry, % of plan (expenses; ministries with a {year} plan of EUR 1 bn or more)",
                 loc="left", fontsize=10.5, fontweight="bold")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("% vs plan (colour capped at +/-25)")
    fig.text(0.01, 0.005, "Blue = below plan (under-spend), red = above plan. 2020-2022 are the pandemic and energy-crisis budgets. "
             "Ministry boundaries changed over time (e.g. 12, 17, 25, 30).", fontsize=8, color=TOTAL)
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def forecast_backtest(bt: pd.DataFrame, crisis_years, out: Path, outlook_text: str = "") -> Path:
    style = {"plan": ("Plan taken at face value", "#1f2933", "-", 2.4),
             "ratio_shrunk_3": ("Plan x half the 3-yr execution ratio", BELOW, "-", 1.6),
             "ratio_mean_3": ("Plan x 3-yr mean execution ratio", ABOVE, "--", 1.6),
             "last_actual": ("Last year's actual", "#9aa5ad", ":", 1.8)}
    fig, ax = plt.subplots(figsize=(10.5, 5))
    years = sorted(bt["year"].unique())
    ax.axvspan(min(crisis_years) - 0.5, max(crisis_years) + 0.5, color="#eef0f2", zorder=0)
    for m, (label, color, ls, lw) in style.items():
        d = bt[bt["method"] == m].sort_values("year")
        ax.plot(d["year"], d["wape"] * 100, color=color, ls=ls, lw=lw, marker="o", ms=3.5, label=label)
    ax.set_xticks(years)
    ax.set_ylabel("Error of forecast, % of actual spend\n(sum of ministry errors / total actual)")
    ax.set_title("Rolling backtest: forecasting year-end actuals per ministry from the plan and prior execution",
                 loc="left", fontsize=10.5, fontweight="bold")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.93))
    ax.text(min(crisis_years), ax.get_ylim()[1] * 0.985, "crisis budgets", ha="left", va="top", fontsize=8, color=TOTAL)
    if outlook_text:
        fig.text(0.01, 0.005, outlook_text, fontsize=8, color=TOTAL)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
