"""Render README.md from results.json numbers, so that no figure in the text is typed by hand."""
from __future__ import annotations

from pathlib import Path

from .analysis import LINE_MIN_EUR, MINISTRY_MIN_PLAN, PCT_THRESHOLD


def _bn(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}"


def _signed(x: float, d: int = 1) -> str:
    return f"{x:+,.{d}f}".replace("-", "−")


def _pct(x: float, d: int = 1) -> str:
    return f"{x:.{d}f} %"


def _spct(x: float, d: int = 1) -> str:
    return f"{x:+.{d}f} %".replace("-", "−")


def render(results: dict, frames: dict) -> str:
    r, L, H, F, C, S = results, results["latest"], results["history"], results["forecast"], results["checks"], results["source"]
    y = r["year"]
    b = L["buckets"]
    planned_mult = L["planned_vs_net_multiple"]
    thr = int(PCT_THRESHOLD * 100)
    line_min = int(LINE_MIN_EUR / 1e6)
    big = int(MINISTRY_MIN_PLAN / 1e9)

    # tables ------------------------------------------------------------------------------------------
    names = {"planned_and_booked": "Planned lines, booked", "planned_not_booked": "Planned, nothing booked",
             "renumbered": "Re-numbered lines (net)", "savings_target": "Global savings targets (negative plan)",
             "unplanned": "Booked without a plan line"}
    order = ["planned_and_booked", "planned_not_booked", "renumbered", "savings_target", "unplanned"]
    t_bucket = "\n".join(f"| {names[k]} | {b[k]['lines']:,} | {_signed(b[k]['variance_bn'])} |" for k in order)

    m = frames["ministries"]
    sel = list(m.head(4).index) + list(m.tail(3).index)
    t_min = "\n".join(
        f"| {m.loc[i, 'ep_label']} ({m.loc[i, 'ep_id']}) | {_bn(m.loc[i, 'soll'] / 1e9)} | {_bn(m.loc[i, 'ist'] / 1e9)} | "
        f"{_signed(m.loc[i, 'variance'] / 1e9, 2)} | {_spct(m.loc[i, 'variance_pct'] * 100)} |" for i in sel)

    cat = frames["categories"]
    t_cat = "\n".join(
        f"| {c.hauptgruppe} {c.hauptgruppe_label} | {_bn(c.soll / 1e9)} | {_bn(c.ist / 1e9)} | {_signed(c.variance / 1e9)} |"
        for c in cat.itertuples())

    top = frames["top_lines"].head(6)
    t_top = "\n".join(
        f"| {t.titel_label[:78]} | {t.ep_label} | {_bn(t.soll / 1e9, 2)} | {_bn(t.ist / 1e9, 2)} | {_signed(t.variance / 1e9, 2)} |"
        for t in top.itertuples())

    tot = frames["totals"]
    t_hist = "\n".join(
        f"| {int(t.year)} | {_bn(t.soll / 1e9)} | {_bn(t.ist / 1e9)} | {_signed(t.variance / 1e9)} | "
        f"{_spct(t.variance_pct * 100)} | {_bn(t.gross_ministry_deviation / 1e9)} |" for t in tot.itertuples())

    labels = {"plan": "Plan at face value", "ratio_shrunk_3": "Plan x half the 3-year execution ratio",
              "ratio_mean_3": "Plan x 3-year mean execution ratio", "ratio_median_3": "Plan x 3-year median ratio",
              "ratio_mean_5": "Plan x 5-year mean execution ratio", "last_actual": "Last year's actual"}
    t_fc = "\n".join(
        f"| {labels[k]} | {_pct(F['wape_all'][k])} | {_pct(F['wape_calm'][k])} | {_pct(F['total_abs_error_all'][k])} | "
        f"{_pct(F['total_abs_error_calm'][k])} |" for k in labels)
    crisis = f"{F['crisis_years'][0]}-{F['crisis_years'][-1]}"
    inc = L["income_largest_shortfall"]

    return f"""# Budget vs actual: variance analysis of the German federal budget

A finance-controlling case on real public data: where did the German federal government spend differently
from its plan in {y}, what drove it, how well can year-end actuals be forecast from the plan, and can the
numbers be trusted?

**Headline:** the federal government spent **EUR {_bn(-L['net_variance_bn'])} bn ({_pct(-L['net_variance_pct'])}) less than planned** in {y}
(plan EUR {_bn(L['plan_bn'])} bn, actual EUR {_bn(L['actual_bn'])} bn). That net figure hides the real picture: lines that were
in the plan were under-spent by **EUR {_bn(-L['planned_lines_variance_bn'])} bn, {planned_mult:.1f} times the net number**. Global savings
targets that are never booked (EUR {_bn(b['savings_target']['variance_bn'])} bn) and spending on lines without a plan entry
(EUR {_bn(b['unplanned']['variance_bn'])} bn) offset the rest. {L['material_lines']} lines under-spent by more than {thr} % and EUR {line_min} m,
together EUR {_bn(-L['material_lines_bn'])} bn. One level up the signal disappears: only {L['ministries_under_10pct']} of {L['ministries']} ministries
were more than {thr} % under plan, and they total EUR {_bn(-L['ministries_under_10pct_bn'], 2)} bn.

| Deliverable | File |
|---|---|
| Controller workbook with live formulas, year selector and materiality inputs | [`reports/budget_variance_workbook.xlsx`](reports/budget_variance_workbook.xlsx) |
| Variance bridge (plan to actual, by ministry and by driver) | [`reports/variance_bridge_{y}.png`](reports/variance_bridge_{y}.png) |
| Actual vs plan by ministry and year | [`reports/execution_heatmap.png`](reports/execution_heatmap.png) |
| Rolling forecast backtest | [`reports/forecast_backtest.png`](reports/forecast_backtest.png) |
| All numbers quoted here | [`reports/results.json`](reports/results.json) |
| SQL (DuckDB): line facts, variance views, drivers, reconciliation checks | [`sql/`](sql/) |

![Variance bridge](reports/variance_bridge_{y}.png)

## Data

| | |
|---|---|
| Source | German federal budget, Federal Ministry of Finance: [bundeshaushalt.de]({S['url']}) |
| What | Plan (Soll) and actual (Ist, from the budget accounts) for expenses and income, by Einzelplan (ministry), Kapitel (chapter) and Titel (line item), {S['years']} |
| Access | The public JSON interface behind the site, the same data as its [download portal]({S['download_portal']}); fetched by [`src/bvc/download.py`](src/bvc/download.py) |
| Licence | The ministry states on the download portal that the data are public and not subject to copyright and may be used, copied, distributed, processed and combined with other data, also commercially. The binding documents are the official budget documents. |
| Downloaded | {S['downloaded_on']} (figures are revised by the source from time to time) |
| Size | {S['nodes']:,} plan and actual values across the three levels; {S['budget_lines_latest_year']:,} expense lines in {y} |

The cleaned tables are in `data/processed/` (4 MB). The raw JSON cache (about 90 MB) is not in the repository:
`python -m bvc.download` rebuilds it.

## Results

### 1. The net variance and what is behind it ({y}, expenses, EUR bn)

Variance = actual minus plan, so negative means under-spent. Every budget line falls into exactly one bucket, so the
buckets add up to the net variance of {_signed(L['net_variance_bn'])} bn:

| Driver | Lines | Variance |
|---|---:|---:|
{t_bucket}

- Planned lines (booked, nothing booked, re-numbered) together are **{_signed(L['planned_lines_variance_bn'])} bn**.
- Across all {L['lines_total']:,} lines the gross deviation (sum of absolute variances) is EUR {_bn(L['gross_line_deviation_bn'])} bn; the 20 largest lines
  explain {L['top20_share_of_gross'] * 100:.0f} % of it.
- The budget data contain no prices or quantities, so a price/volume split is not possible. The driver split above
  (line type) and the category split below are what the data support.

### 2. By ministry and by category ({y})

| Ministry (Einzelplan) | Plan | Actual | Variance | % |
|---|---:|---:|---:|---:|
{t_min}

(the 4 largest under-spends and the 3 largest over-spends of {L['ministries']} ministries; full table in the workbook)

{L['largest_under']['label']} and {L['second_under']['label']} explain {L['top2_ministries_share_of_net'] * 100:.0f} % of the net variance.
{L['ministries_over_plan']} of {L['ministries']} ministries spent more than planned, so ministry totals also net out against each other:
the sum of absolute ministry variances is EUR {_bn(L['gross_ministry_deviation_bn'])} bn against a net EUR {_bn(-L['net_variance_bn'])} bn.

| Category (Hauptgruppe) | Plan | Actual | Variance |
|---|---:|---:|---:|
{t_cat}

### 3. Largest line-item deviations ({y}; official line names, in German)

| Line (Titel) | Ministry | Plan | Actual | Variance |
|---|---|---:|---:|---:|
{t_top}

### 4. History {S['years']} (expenses, EUR bn)

| Year | Plan | Actual | Variance | % | Sum of absolute ministry variances |
|---|---:|---:|---:|---:|---:|
{t_hist}

- Actual was below plan in {H['years_under_plan']} of {H['years']} years. Outside {crisis} the average net variance is only {_spct(H['avg_net_pct_ex_crisis'], 2)}:
  the total is usually close to plan, so the interesting variance sits underneath it. The sum of absolute ministry variances is a median of
  {H['median_gross_to_net']:.1f} times the absolute net variance.
- 2020 is the outlier: EUR {_bn(-H['crisis_2020_variance_bn'])} bn ({_pct(-H['crisis_2020_pct'])}) below a plan that had been raised by supplementary budgets during the pandemic.
- Income side ({y}): the budget is balanced by law, so total income equals total expenses in both plan and actual.
  The largest income variance is {inc['label']} ({_signed(inc['bn'])} bn, {_spct(inc['pct'])}), the receipts category that carries borrowing, coming in below plan.

![Execution heat map](reports/execution_heatmap.png)

### 5. Forecasting year-end actuals

The source has annual figures only, so this is a start-of-year forecast rather than an in-year roll-forward from monthly
execution: for each year, given that year's plan and the execution of earlier years, what will be spent? It is tested with a
rolling origin ({F['n_test_years']} test years, {F['test_years']}): each year is forecast with data from earlier years only.
Error = sum of absolute ministry errors / total actual spend.

| Method | Ministry error, all years | Ministry error, excl. {crisis} | Total error, all years | Total error, excl. {crisis} |
|---|---:|---:|---:|---:|
{t_fc}

- **The plan itself is a hard benchmark.** Taken at face value it is off by {_pct(F['wape_all']['plan'])} per ministry ({_pct(F['wape_calm']['plan'])} without the crisis years)
  and by {_pct(F['total_abs_error_calm']['plan'])} in total. Adjusting it with past execution ratios helps in calm years only marginally
  ({F['best_calm'].replace('_', ' ')} {_pct(F['wape_calm'][F['best_calm']])} vs {_pct(F['wape_calm']['plan'])}) and loses over all years.
  Using last year's actual is clearly worst.
- {y} backtest: plan error {_pct(F['plan_wape_last'])} per ministry, {_spct(F['plan_total_error_last'])} in total (forecast minus actual, relative to actual).
- **Outlook {F['outlook_year']}:** adopted plan EUR {_bn(F['outlook_plan_bn'])} bn. With the range of past non-crisis total errors
  ({_spct(F['outlook_err_lo_pct'])} to {_spct(F['outlook_err_hi_pct'])}) the expected actual is EUR {_bn(F['outlook_low_bn'])} to {_bn(F['outlook_high_bn'])} bn
  (the alternative method gives EUR {_bn(F['outlook_shrunk_bn'])} bn). This is a planning range, not a prediction.

![Forecast backtest](reports/forecast_backtest.png)

### 6. Can the numbers be trusted? Reconciliation checks

Eight checks written as SQL views ([`sql/07_reconciliation.sql`](sql/07_reconciliation.sql)), run over every year, plan and actual, expenses and income.
**{C['passed']} of {C['total']} pass on the official data** (no violations): totals tie from line item to chapter to ministry to
total; line items per category tie to the source's own category totals (an independent aggregation); total expenses equal total income;
no missing parents or malformed codes; no duplicates; category codes valid; no unexplained negative expense line above EUR 1 bn;
full year coverage. Negative expense lines do exist (bond discounts, refunded Covid aid, global savings targets); they stay below
{C['negative_expense_share_actual_max_pct']:.1f} % of actual spending in any year and are covered by a documented allow-list.
The tests also tamper with a copy of the data and require each check to catch it, so a passing check means something.

## Method

| Step | File |
|---|---|
| Download plan and actual, all levels, with retries and an on-disk cache | [`src/bvc/download.py`](src/bvc/download.py) |
| Load into DuckDB, build facts and views | [`src/bvc/data.py`](src/bvc/data.py), [`sql/`](sql/) |
| Variance, decomposition, bridge (pure pandas) | [`src/bvc/calc.py`](src/bvc/calc.py) |
| Rolling-origin forecast and backtest | [`src/bvc/forecast.py`](src/bvc/forecast.py) |
| Reconciliation checks | [`sql/07_reconciliation.sql`](sql/07_reconciliation.sql), [`src/bvc/checks.py`](src/bvc/checks.py) |
| Analysis, charts, workbook, this README | [`src/bvc/analysis.py`](src/bvc/analysis.py), [`charts.py`](src/bvc/charts.py), [`excel.py`](src/bvc/excel.py), [`readme.py`](src/bvc/readme.py) |
| Rebuild everything | `python -m bvc.build` |
| Tests: checks pass on the real data and fail on tampered data, variance identities, the bridge closes, the forecast does not look ahead, the workbook recalculates to the same numbers, README figures equal `results.json` | [`tests/`](tests/) |

Choices worth defending:

- **Planned and unplanned are separated.** In the plan, negative lines (global savings targets) are (almost) never booked, so they appear
  as an over-spend of the same size and hide real under-spends. Splitting them out is what turns EUR {_bn(-L['net_variance_bn'])} bn into EUR {_bn(-L['planned_lines_variance_bn'])} bn.
- **Materiality needs two limits.** More than {thr} % alone flags tiny budgets (Federal President, Federal Council); more than an amount alone
  flags large budgets that are on plan. Both limits are inputs in the workbook.
- **Re-numbered lines are matched** on ministry and identical title text within a year, so a line that moved to another number
  is not counted as one under-spend plus one unplanned spend.
- **The checks use two independent routes** (sum of children, and the source's own category totals) rather than one.
- **The forecast is compared with the plan, not with nothing.** An adjusted forecast is only worth having if it beats the budget as written.

## Limits

- **Annual data only.** No monthly or quarterly execution, so there is no in-year roll-forward; the forecast is made at the start of the year.
  Monthly cash reports of the Ministry of Finance would be the next data source.
- **The plan is the published plan including supplementary budgets**, not adjusted for carried-over funds (Haushaltsreste, Ausgabereste).
  Spending of carried-over funds shows up under "booked without a plan line".
- **No price/volume decomposition**: budget lines carry no quantities or prices.
- **Ministry boundaries move** (for example 2021/22 and 2025 reorganisations). Series are compared by Einzelplan number and show the
  latest name, so a few ministry-level year-on-year comparisons are not like for like.
- **Technical items are not controllable spend.** General Financial Administration and Federal Debt contain reserves, savings targets and debt
  service; a controller would often analyse them separately.
- **Ministries over EUR {big} bn:** the {big} bn cut-off for "large" is a choice; with {L['large_ministries_under_10pct']} large ministries under-spending by more than {thr} %, the conclusion does not depend on it.
- **Small backtest:** {F['n_test_years']} test years, {len(F['crisis_years'])} of them crisis years. The difference between the best adjusted method and the plan in calm years is small and not statistically meaningful.
- The negative-line allow-list was written after looking at the data.
- Line matching for re-numbered items uses exact text and will miss renamed lines.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
python -m bvc.download     # optional: re-download (about 12,000 requests, cached in data/raw/cache)
python -m bvc.build        # results.json, workbook, charts, this README, from data/processed
python -m pytest -q
```

Every number above comes from `reports/results.json`, produced by `python -m bvc.build`, and a test fails if this README and the code disagree.
"""


def write(results: dict, frames: dict, path: Path) -> Path:
    path.write_text(render(results, frames), encoding="utf-8")
    return path
