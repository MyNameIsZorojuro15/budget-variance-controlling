"""Rebuild everything from data/processed: results.json, workbook, charts and README.

    python -m bvc.build
"""
from __future__ import annotations

import json
from pathlib import Path

from . import charts, excel, readme
from .analysis import analyse
from .data import ROOT, connect

REPORTS = ROOT / "reports"


def main() -> dict:
    REPORTS.mkdir(exist_ok=True)
    con = connect()
    results, frames = analyse(con)
    y = results["year"]
    (REPORTS / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    charts.variance_bridge(frames["bridge_ministry"], frames["bridge_bucket"], y, REPORTS / f"variance_bridge_{y}.png")
    charts.execution_heatmap(frames["heat"], y, REPORTS / "execution_heatmap.png")
    f = results["forecast"]
    charts.forecast_backtest(
        frames["backtest"], f["crisis_years"], REPORTS / "forecast_backtest.png",
        f"Outlook {f['outlook_year']}: plan EUR {f['outlook_plan_bn']:.1f} bn, expected actual EUR "
        f"{f['outlook_low_bn']:.1f} to {f['outlook_high_bn']:.1f} bn (range of past non-crisis errors).")
    excel.build_workbook(results, frames, REPORTS / "budget_variance_workbook.xlsx")
    readme.write(results, frames, ROOT / "README.md")
    print(f"built {REPORTS}")
    return results


if __name__ == "__main__":
    main()
