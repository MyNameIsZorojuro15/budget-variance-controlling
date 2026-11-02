"""Controller workbook: live formulas on top of data sheets, with a year selector and materiality inputs.

Sheets: Summary, Variance (year selector), Categories, Drivers, Bridge (with waterfall chart), Top_Lines,
Forecast (backtest and outlook with editable error band), Checks (reconciliation), Data_* (inputs).
All amounts in EUR million. Variance = Ist - Soll.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HEAD = PatternFill("solid", fgColor="2F3B45")
INPUT = PatternFill("solid", fgColor="FFF4C2")
BAND = PatternFill("solid", fgColor="EEF1F3")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
BLUE = Font(color="2B6A99")
ORANGE = Font(color="C0651A")
THIN = Side(style="thin", color="C9D0D6")
EUR = '#,##0.0;[Color10]-#,##0.0;"-"'
NUM = '#,##0.0;-#,##0.0;"-"'
PCT = '0.0%;-0.0%;0.0%'
BUCKET_NAMES = {"planned_and_booked": "Planned lines, booked", "planned_not_booked": "Planned, nothing booked",
                "savings_target": "Global savings targets (negative plan)", "unplanned": "Booked without a plan line",
                "renumbered": "Re-numbered lines (net)"}
BUCKET_TEXT = {
    "planned_and_booked": "In the plan and booked: the spending rate differs from plan.",
    "planned_not_booked": "Positive plan amount, nothing booked: unused provisions, cancelled or delayed measures.",
    "savings_target": "Negative plan lines (e.g. Globale Minderausgabe): never booked as such, so always a positive variance.",
    "unplanned": "Booked on a line with no plan entry that year: carried-over funds, new lines.",
    "renumbered": "Unplanned and not-booked line with the same ministry and title text: moved line, net effect.",
}
METHOD_NAMES = {"plan": "Plan at face value", "ratio_shrunk_3": "Plan x half the 3-yr execution ratio",
                "ratio_mean_3": "Plan x 3-yr mean execution ratio", "ratio_median_3": "Plan x 3-yr median ratio",
                "ratio_mean_5": "Plan x 5-yr mean execution ratio", "last_actual": "Last year's actual"}


def _hdr(ws, row: int, labels: list[str], col: int = 1) -> None:
    for i, t in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=t)
        c.fill, c.font = HEAD, WHITE
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 32


def _widths(ws, widths: dict) -> None:
    for k, v in widths.items():
        ws.column_dimensions[k].width = v


def _title(ws, text: str, sub: str = "") -> None:
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="5B6770")


def _signed_colours(ws, rng: str) -> None:
    ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"], font=BLUE))
    ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], font=ORANGE))


def build_workbook(results: dict, frames: dict, path: Path) -> Path:
    wb = Workbook()
    y = results["year"]
    ep = frames["ep_all"]
    exp = ep[ep["account"] == "expenses"].copy()
    years = sorted(exp["year"].unique().tolist())
    eps = (exp[exp["year"] == y].sort_values("variance")[["ep_id", "ep_label"]].drop_duplicates().values.tolist())
    seen = {e for e, _ in eps}
    eps += [[e, l] for e, l in exp[~exp["ep_id"].isin(seen)][["ep_id", "ep_label"]].drop_duplicates().values.tolist()]
    nm = lambda e: f"EP{e}"  # noqa: E731  text key so Excel never reads "01" as the number 1

    # ---------------- data sheets -----------------------------------------------------------------
    d_ep = wb.active
    d_ep.title = "Data_EP"
    _hdr(d_ep, 1, ["Year", "Key", "Ministry", "Plan (Soll) EUR m", "Actual (Ist) EUR m"])
    for i, r in enumerate(exp.sort_values(["year", "ep_id"]).itertuples(), start=2):
        d_ep.append([int(r.year), nm(r.ep_id), r.ep_label, r.soll / 1e6, r.ist / 1e6])
    n_ep = d_ep.max_row
    _widths(d_ep, {"A": 8, "B": 8, "C": 60, "D": 18, "E": 18})
    d_ep.freeze_panes = "A2"

    cat = (frames["cat_all"]).copy()
    d_cat = wb.create_sheet("Data_Cat")
    _hdr(d_cat, 1, ["Year", "Key", "Hauptgruppe", "Category", "Plan (Soll) EUR m", "Actual (Ist) EUR m"])
    for r in cat.itertuples():
        d_cat.append([int(r.year), nm(r.ep_id), str(r.hauptgruppe), r.hauptgruppe_label, r.soll / 1e6, r.ist / 1e6])
    n_cat = d_cat.max_row
    _widths(d_cat, {"A": 8, "B": 8, "C": 12, "D": 60, "E": 18, "F": 18})
    d_cat.freeze_panes = "A2"

    ba = frames["buckets_all"]
    d_bk = wb.create_sheet("Data_Bucket")
    _hdr(d_bk, 1, ["Year", "Bucket", "Lines", "Plan (Soll) EUR m", "Actual (Ist) EUR m"])
    for r in ba.itertuples():
        d_bk.append([int(r.year), r.bucket, int(r.lines), r.soll / 1e6, r.ist / 1e6])
    n_bk = d_bk.max_row
    _widths(d_bk, {"A": 8, "B": 22, "C": 8, "D": 18, "E": 18})

    tot = frames["totals_reported"]
    d_tot = wb.create_sheet("Data_Totals")
    _hdr(d_tot, 1, ["Year", "Reported total plan EUR m", "Reported total actual EUR m"])
    for r in tot.itertuples():
        d_tot.append([int(r.year), r.soll / 1e6, r.ist / 1e6])
    n_tot = d_tot.max_row
    _widths(d_tot, {"A": 8, "B": 26, "C": 26})

    # ---------------- Variance ---------------------------------------------------------------------
    ws = wb.create_sheet("Variance", 0)
    _title(ws, "Budget vs actual by ministry (Einzelplan), expenses",
           "Pick a year in the yellow cell. Variance = Ist - Soll: negative = under-spent. EUR million.")
    ws["A3"], ws["A4"], ws["A5"] = "Year", "Flag if variance beyond (%)", "... and beyond (EUR m)"
    ws["C3"], ws["C4"], ws["C5"] = y, 0.10, 100
    for c in ("C3", "C4", "C5"):
        ws[c].fill = INPUT
        ws[c].font = BOLD
    ws["C4"].number_format = "0%"
    dv = DataValidation(type="list", formula1='"' + ",".join(str(v) for v in years) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("C3")
    _hdr(ws, 7, ["Key", "Ministry", "Plan (Soll)", "Actual (Ist)", "Variance", "Variance %", "Flag", "Share of net variance"])
    first, last = 8, 8 + len(eps) - 1
    for i, (e, label) in enumerate(eps):
        r = first + i
        ws.cell(r, 1, nm(e))
        ws.cell(r, 2, label)
        ws.cell(r, 3, f"=SUMIFS(Data_EP!$D$2:$D${n_ep},Data_EP!$A$2:$A${n_ep},$C$3,Data_EP!$B$2:$B${n_ep},$A{r})")
        ws.cell(r, 4, f"=SUMIFS(Data_EP!$E$2:$E${n_ep},Data_EP!$A$2:$A${n_ep},$C$3,Data_EP!$B$2:$B${n_ep},$A{r})")
        ws.cell(r, 5, f"=D{r}-C{r}")
        ws.cell(r, 6, f'=IF(C{r}=0,"",E{r}/C{r})')
        ws.cell(r, 7, f'=IF(C{r}=0,"",IF(AND(ABS(F{r})>$C$4,ABS(E{r})>$C$5),IF(E{r}<0,"Under-spent","Over-spent"),""))')
        ws.cell(r, 8, f'=IF($E${last + 1}=0,"",E{r}/$E${last + 1})')
        for c in (3, 4, 5):
            ws.cell(r, c).number_format = EUR if c == 5 else NUM
        ws.cell(r, 6).number_format = PCT
        ws.cell(r, 8).number_format = PCT
    t = last + 1
    ws.cell(t, 2, "Total").font = BOLD
    for c, L in ((3, "C"), (4, "D"), (5, "E")):
        ws.cell(t, c, f"=SUM({L}{first}:{L}{last})").font = BOLD
        ws.cell(t, c).number_format = NUM
    ws.cell(t, 6, f'=IF(C{t}=0,"",E{t}/C{t})').number_format = PCT
    for c in range(1, 9):
        ws.cell(t, c).border = Border(top=THIN)
    ws.cell(t + 2, 2, "Reported total (source, level 0)").font = Font(italic=True)
    ws.cell(t + 2, 3, f"=SUMIFS(Data_Totals!$B$2:$B${n_tot},Data_Totals!$A$2:$A${n_tot},$C$3)").number_format = NUM
    ws.cell(t + 2, 4, f"=SUMIFS(Data_Totals!$C$2:$C${n_tot},Data_Totals!$A$2:$A${n_tot},$C$3)").number_format = NUM
    ws.cell(t + 3, 2, "Difference to sum of ministries (should be 0)").font = Font(italic=True)
    ws.cell(t + 3, 3, f"=ROUND(C{t}-C{t + 2},3)").number_format = NUM
    ws.cell(t + 3, 4, f"=ROUND(D{t}-D{t + 2},3)").number_format = NUM
    ws.cell(t + 4, 2, "Ministries flagged / of which under-spent").font = Font(italic=True)
    ws.cell(t + 4, 3, f'=COUNTIF(G{first}:G{last},"?*")')
    ws.cell(t + 4, 4, f'=COUNTIF(G{first}:G{last},"Under-spent")')
    _signed_colours(ws, f"E{first}:F{last}")
    ws.conditional_formatting.add(f"G{first}:G{last}", FormulaRule(formula=[f'G{first}="Under-spent"'],
                                  fill=PatternFill("solid", bgColor="CFE2F3")))
    ws.conditional_formatting.add(f"G{first}:G{last}", FormulaRule(formula=[f'G{first}="Over-spent"'],
                                  fill=PatternFill("solid", bgColor="F9DCC4")))
    ws.auto_filter.ref = f"A7:H{last}"
    ws.freeze_panes = "C8"
    _widths(ws, {"A": 8, "B": 60, "C": 14, "D": 14, "E": 14, "F": 12, "G": 14, "H": 14})
    var_total_cell = f"Variance!$E${t}"

    # ---------------- Categories --------------------------------------------------------------------
    wc = wb.create_sheet("Categories")
    _title(wc, "Variance by economic category (Hauptgruppe)", "Follows the year selected on the Variance sheet. EUR million.")
    wc["A3"], wc["C3"] = "Year", "=Variance!C3"
    cats = [(h, l) for h, l in frames["categories"][["hauptgruppe", "hauptgruppe_label"]].values.tolist()]
    _hdr(wc, 5, ["Group", "Category", "Plan (Soll)", "Actual (Ist)", "Variance", "Variance %"])
    for i, (h, l) in enumerate(cats):
        r = 6 + i
        wc.cell(r, 1, str(h))
        wc.cell(r, 2, l)
        wc.cell(r, 3, f"=SUMIFS(Data_Cat!$E$2:$E${n_cat},Data_Cat!$A$2:$A${n_cat},$C$3,Data_Cat!$C$2:$C${n_cat},$A{r})")
        wc.cell(r, 4, f"=SUMIFS(Data_Cat!$F$2:$F${n_cat},Data_Cat!$A$2:$A${n_cat},$C$3,Data_Cat!$C$2:$C${n_cat},$A{r})")
        wc.cell(r, 5, f"=D{r}-C{r}")
        wc.cell(r, 6, f'=IF(C{r}=0,"",E{r}/ABS(C{r}))')
    cl = 6 + len(cats) - 1
    wc.cell(cl + 1, 2, "Total").font = BOLD
    for c, L in ((3, "C"), (4, "D"), (5, "E")):
        wc.cell(cl + 1, c, f"=SUM({L}6:{L}{cl})").font = BOLD
    wc.cell(cl + 2, 2, "Difference to Variance sheet (should be 0)").font = Font(italic=True)
    wc.cell(cl + 2, 5, f"=ROUND(E{cl + 1}-{var_total_cell},3)")
    for r in range(6, cl + 3):
        for c in (3, 4, 5):
            wc.cell(r, c).number_format = NUM
        wc.cell(r, 6).number_format = PCT
    wc.cell(cl + 4, 2, "Group 9 carries the global savings targets (negative plan); see the Drivers sheet.").font = Font(italic=True)
    m0 = cl + 6
    wc.cell(m0 - 1, 1, "Variance by ministry and category").font = BOLD
    _hdr(wc, m0, ["Key", "Ministry"] + [f"Group {h}" for h, _ in cats] + ["Total"])
    for i, (e, label) in enumerate(eps):
        r = m0 + 1 + i
        wc.cell(r, 1, nm(e))
        wc.cell(r, 2, label)
        for j, (h, _) in enumerate(cats):
            col = 3 + j
            wc.cell(r, col, (f"=SUMIFS(Data_Cat!$F$2:$F${n_cat},Data_Cat!$A$2:$A${n_cat},$C$3,Data_Cat!$B$2:$B${n_cat},$A{r},"
                             f"Data_Cat!$C$2:$C${n_cat},\"{h}\")-SUMIFS(Data_Cat!$E$2:$E${n_cat},Data_Cat!$A$2:$A${n_cat},$C$3,"
                             f"Data_Cat!$B$2:$B${n_cat},$A{r},Data_Cat!$C$2:$C${n_cat},\"{h}\")")).number_format = EUR
        wc.cell(r, 3 + len(cats), f"=SUM(C{r}:{get_column_letter(2 + len(cats))}{r})").number_format = EUR
    mend = m0 + len(eps)
    _signed_colours(wc, f"C{m0 + 1}:{get_column_letter(3 + len(cats))}{mend}")
    _widths(wc, {"A": 8, "B": 60, "C": 14, "D": 14, "E": 14, "F": 14, "G": 14, "H": 14, "I": 14})
    wc.freeze_panes = "C6"

    # ---------------- Drivers -----------------------------------------------------------------------
    wd = wb.create_sheet("Drivers")
    _title(wd, "What drives the variance? Every budget line sits in exactly one bucket",
           "Follows the year selected on the Variance sheet. EUR million. The buckets add up to the total variance.")
    wd["A3"], wd["C3"] = "Year", "=Variance!C3"
    _hdr(wd, 5, ["Bucket", "Description", "Lines", "Plan (Soll)", "Actual (Ist)", "Variance", "Share of net variance"])
    order = ["planned_and_booked", "planned_not_booked", "renumbered", "savings_target", "unplanned"]
    for i, b in enumerate(order):
        r = 6 + i
        wd.cell(r, 1, b)
        wd.cell(r, 2, f"{BUCKET_NAMES[b]}: {BUCKET_TEXT[b]}").alignment = Alignment(wrap_text=True, vertical="top")
        rng = lambda col: f"Data_Bucket!${col}$2:${col}${n_bk}"  # noqa: E731
        wd.cell(r, 3, f"=SUMIFS({rng('C')},{rng('A')},$C$3,{rng('B')},$A{r})")
        wd.cell(r, 4, f"=SUMIFS({rng('D')},{rng('A')},$C$3,{rng('B')},$A{r})")
        wd.cell(r, 5, f"=SUMIFS({rng('E')},{rng('A')},$C$3,{rng('B')},$A{r})")
        wd.cell(r, 6, f"=E{r}-D{r}")
        wd.cell(r, 7, f'=IF($F$11=0,"",F{r}/$F$11)')
        wd.row_dimensions[r].height = 44
    wd.cell(11, 1, "Total").font = BOLD
    for c, L in ((3, "C"), (4, "D"), (5, "E"), (6, "F")):
        wd.cell(11, c, f"=SUM({L}6:{L}10)").font = BOLD
    wd.cell(12, 1, "Planned lines only (booked + not booked + re-numbered)").font = Font(italic=True)
    wd.cell(12, 6, "=F6+F7+F8")
    wd.cell(13, 1, "... as a multiple of the net variance").font = Font(italic=True)
    wd.cell(13, 6, '=IF(F11=0,"",F12/F11)').number_format = '0.0"x"'
    wd.cell(14, 1, "Difference to Variance sheet (should be 0)").font = Font(italic=True)
    wd.cell(14, 6, f"=ROUND(F11-{var_total_cell},3)")
    for r in range(6, 13):
        for c in (4, 5, 6):
            wd.cell(r, c).number_format = EUR if c == 6 else NUM
        wd.cell(r, 7).number_format = PCT
    wd.cell(14, 6).number_format = NUM
    _signed_colours(wd, "F6:F12")
    _widths(wd, {"A": 22, "B": 70, "C": 10, "D": 14, "E": 14, "F": 14, "G": 14})

    # ---------------- Bridge ------------------------------------------------------------------------
    wbg = wb.create_sheet("Bridge")
    _title(wbg, f"Variance bridge {y}: plan to actual by ministry (largest deviations)",
           "Static for the latest year; start/end/chart helper columns are formulas. EUR million.")
    br = frames["bridge_ministry"]
    _hdr(wbg, 4, ["Step", "Kind", "Value", "Start", "End", "Base (hidden)", "Below plan", "Above plan", "Total"])
    b0 = 5
    for i, r in enumerate(br.itertuples()):
        row = b0 + i
        wbg.cell(row, 1, r.step)
        wbg.cell(row, 2, r.kind)
        wbg.cell(row, 3, r.value / 1e6)
        if r.kind == "total":
            wbg.cell(row, 4, 0)
            wbg.cell(row, 5, f"=C{row}")
            wbg.cell(row, 6, 0)
            wbg.cell(row, 9, f"=E{row}")
            wbg.cell(row, 7, 0)
            wbg.cell(row, 8, 0)
        else:
            wbg.cell(row, 4, f"=E{row - 1}")
            wbg.cell(row, 5, f"=D{row}+C{row}")
            wbg.cell(row, 6, f"=MIN(D{row},E{row})")
            wbg.cell(row, 7, f"=IF(C{row}<0,-C{row},0)")
            wbg.cell(row, 8, f"=IF(C{row}>0,C{row},0)")
            wbg.cell(row, 9, 0)
        for c in range(3, 10):
            wbg.cell(row, c).number_format = NUM
    bl = b0 + len(br) - 1
    wbg.cell(bl + 2, 1, "Check: plan + steps - actual (should be 0)").font = Font(italic=True)
    wbg.cell(bl + 2, 3, f"=ROUND(C{b0}+SUM(C{b0 + 1}:C{bl - 1})-C{bl},3)").number_format = NUM
    ch = BarChart()
    ch.type, ch.grouping, ch.overlap = "col", "stacked", 100
    ch.title = f"Federal expenses {y}: plan to actual (EUR m)"
    cats_ref = Reference(wbg, min_col=1, min_row=b0, max_row=bl)
    for col, colour in ((6, None), (7, "2B6A99"), (8, "D9822B"), (9, "5B6770")):
        ch.add_data(Reference(wbg, min_col=col, min_row=4, max_row=bl), titles_from_data=True)
        s = ch.series[-1]
        if colour is None:
            s.graphicalProperties.noFill = True
            s.graphicalProperties.line.noFill = True
        else:
            s.graphicalProperties.solidFill = colour
    ch.set_categories(cats_ref)
    lo = min(float(br["start"][br["kind"] == "delta"].min()), float(br["end"].min())) / 1e6
    ch.y_axis.scaling.min = float(int((lo - 20000) / 5000) * 5000)
    ch.y_axis.delete = False
    ch.x_axis.delete = False
    ch.legend.position = "b"
    ch.height, ch.width = 9.5, 24
    wbg.add_chart(ch, f"A{bl + 5}")
    _signed_colours(wbg, f"C{b0 + 1}:C{bl - 1}")
    _widths(wbg, {"A": 38, "B": 8, "C": 14, "D": 14, "E": 14, "F": 14, "G": 12, "H": 12, "I": 12})

    # ---------------- Top lines ---------------------------------------------------------------------
    wt = wb.create_sheet("Top_Lines")
    _title(wt, f"Largest line-item deviations {y} (expenses)", "Titel level. EUR million. Variance = Ist - Soll.")
    _hdr(wt, 4, ["#", "Ministry", "Line (Titel)", "Code", "Plan (Soll)", "Actual (Ist)", "Variance", "Variance %", "Status"])
    top = frames["top_lines"]
    for i, r in enumerate(top.itertuples()):
        row = 5 + i
        wt.cell(row, 1, i + 1)
        wt.cell(row, 2, r.ep_label)
        wt.cell(row, 3, r.titel_label)
        wt.cell(row, 4, r.titel_id)
        wt.cell(row, 5, r.soll / 1e6).number_format = NUM
        wt.cell(row, 6, r.ist / 1e6).number_format = NUM
        wt.cell(row, 7, f"=F{row}-E{row}").number_format = EUR
        wt.cell(row, 8, f'=IF(E{row}=0,"",G{row}/ABS(E{row}))').number_format = PCT
        wt.cell(row, 9, r.line_status)
    _signed_colours(wt, f"G5:H{4 + len(top)}")
    wt.freeze_panes = "A5"
    _widths(wt, {"A": 5, "B": 36, "C": 70, "D": 12, "E": 14, "F": 14, "G": 14, "H": 12, "I": 12})

    # ---------------- Forecast ----------------------------------------------------------------------
    wf = wb.create_sheet("Forecast")
    _title(wf, "Forecast of year-end actuals: rolling backtest and outlook",
           "Each test year uses only earlier years' execution. Error = sum of absolute ministry errors / total actual.")
    bt = frames["backtest"]
    methods = [m for m in METHOD_NAMES if m in set(bt["method"])]
    _hdr(wf, 4, ["Test year", "Crisis year (1=yes)"] + [METHOD_NAMES[m] for m in methods])
    pv = bt.pivot(index="year", columns="method", values="wape")
    crisis = set(results["forecast"]["crisis_years"])
    for i, (yr, row) in enumerate(pv.iterrows()):
        r = 5 + i
        wf.cell(r, 1, int(yr))
        wf.cell(r, 2, 1 if int(yr) in crisis else 0)
        for j, m in enumerate(methods):
            wf.cell(r, 3 + j, float(row[m])).number_format = PCT
    fl = 5 + len(pv) - 1
    wf.cell(fl + 1, 1, "Mean, all years").font = BOLD
    wf.cell(fl + 2, 1, "Mean, excluding crisis years").font = BOLD
    for j in range(len(methods)):
        L = get_column_letter(3 + j)
        wf.cell(fl + 1, 3 + j, f"=AVERAGE({L}5:{L}{fl})").number_format = PCT
        wf.cell(fl + 2, 3 + j, f"=AVERAGEIF($B$5:$B${fl},0,{L}5:{L}{fl})").number_format = PCT
    wf.cell(fl + 4, 1, "Reading: if the plan at face value is as good as any adjusted forecast, adjusting for past "
                       "execution ratios adds no value for this budget.").font = Font(italic=True)
    o0 = fl + 7
    out = frames["forecast_outlook"]
    p = results["forecast"]
    wf.cell(o0 - 3, 1, f"Outlook {p['outlook_year']}: expected actuals from the adopted plan").font = Font(bold=True, size=12)
    wf.cell(o0 - 2, 1, "Error band, low (%)")
    wf.cell(o0 - 2, 3, p["outlook_err_lo_pct"] / 100).fill = INPUT
    wf.cell(o0 - 2, 4, "Error band, high (%)")
    wf.cell(o0 - 2, 5, p["outlook_err_hi_pct"] / 100).fill = INPUT
    for c in (3, 5):
        wf.cell(o0 - 2, c).number_format = PCT
    wf.cell(o0 - 2, 6, "Range of (forecast - actual) / actual for the plan method in non-crisis test years; editable.").font = Font(italic=True)
    _hdr(wf, o0, ["Key", "Ministry", f"Plan {p['outlook_year']}", "Forecast actual (plan method)", "Low", "High",
                  "Alt.: plan x half the 3-yr execution ratio"])
    for i, r in enumerate(out.sort_values("plan", ascending=False).itertuples()):
        row = o0 + 1 + i
        wf.cell(row, 1, nm(r.ep_id))
        wf.cell(row, 2, r.label)
        wf.cell(row, 3, r.plan / 1e6)
        wf.cell(row, 4, f"=C{row}")
        wf.cell(row, 5, f"=D{row}/(1+$E${o0 - 2})")
        wf.cell(row, 6, f"=D{row}/(1+$C${o0 - 2})")
        wf.cell(row, 7, (r.ratio_shrunk_3 / 1e6) if pd.notna(r.ratio_shrunk_3) else None)
        for c in range(3, 8):
            wf.cell(row, c).number_format = NUM
    ol = o0 + len(out)
    wf.cell(ol + 1, 2, "Total").font = BOLD
    for c in range(3, 8):
        L = get_column_letter(c)
        wf.cell(ol + 1, c, f"=SUM({L}{o0 + 1}:{L}{ol})").number_format = NUM
        wf.cell(ol + 1, c).font = BOLD
    wf.cell(ol + 2, 2, "Ministries without history (new Einzelplan) are forecast at plan; "
                       "the alternative column leaves them empty.").font = Font(italic=True)
    _widths(wf, {"A": 16, "B": 46, "C": 18, "D": 22, "E": 18, "F": 18, "G": 22, "H": 18})

    # ---------------- Checks ------------------------------------------------------------------------
    wk = wb.create_sheet("Checks")
    _title(wk, "Reconciliation checks", "Run in SQL (sql/07_reconciliation.sql) over every year, plan and actual, expenses and income.")
    _hdr(wk, 4, ["Check", "Violations", "Result"])
    chk = frames["checks"]
    for i, r in enumerate(chk.itertuples()):
        wk.cell(5 + i, 1, r.check)
        wk.cell(5 + i, 2, r.violations)
        wk.cell(5 + i, 3, r.result)
    kl = 5 + len(chk) - 1
    wk.conditional_formatting.add(f"C5:C{kl}", FormulaRule(formula=['C5="PASS"'], fill=PatternFill("solid", bgColor="D5EBD5")))
    wk.conditional_formatting.add(f"C5:C{kl}", FormulaRule(formula=['C5="FAIL"'], fill=PatternFill("solid", bgColor="F4C7C3")))
    wk.cell(kl + 2, 1, "Live tie-out in this workbook (selected year)").font = BOLD
    wk.cell(kl + 3, 1, "Sum of ministries minus reported total, plan (EUR m)")
    wk.cell(kl + 3, 2, "=Variance!C%d" % (t + 3))
    wk.cell(kl + 4, 1, "Sum of ministries minus reported total, actual (EUR m)")
    wk.cell(kl + 4, 2, "=Variance!D%d" % (t + 3))
    wk.cell(kl + 5, 1, "Categories minus ministries, variance (EUR m)")
    wk.cell(kl + 5, 2, "=Categories!E%d" % (cl + 2))
    wk.cell(kl + 6, 1, "Drivers minus ministries, variance (EUR m)")
    wk.cell(kl + 6, 2, "=Drivers!F14")
    wk.cell(kl + 7, 1, "All live checks zero?")
    wk.cell(kl + 7, 2, f'=IF(AND(B{kl + 3}=0,B{kl + 4}=0,B{kl + 5}=0,B{kl + 6}=0),"PASS","FAIL")')
    neg = frames["negative_lines"]
    wk.cell(kl + 9, 1, "Negative expense lines by year (sign check)").font = BOLD
    _hdr(wk, kl + 10, ["Year / quota", "Lines", "Sum EUR m", "Share of total"])
    for i, r in enumerate(neg.itertuples()):
        row = kl + 11 + i
        wk.cell(row, 1, f"{r.year} {'plan' if r.quota == 'target' else 'actual'}")
        wk.cell(row, 2, int(r.lines))
        wk.cell(row, 3, r.negative_total / 1e6).number_format = NUM
        wk.cell(row, 4, float(r.share_of_total)).number_format = PCT
    _widths(wk, {"A": 70, "B": 14, "C": 14, "D": 14})

    # ---------------- Summary -----------------------------------------------------------------------
    s = wb.create_sheet("Summary", 0)
    L = results["latest"]
    _title(s, f"German federal budget {y}: plan vs actual", "Variance analysis workbook. Source: bundeshaushalt.de (Federal Ministry of Finance).")
    rows = [
        ("Plan (Soll), expenses, EUR bn", L["plan_bn"], "0.0"),
        ("Actual (Ist), expenses, EUR bn", L["actual_bn"], "0.0"),
        ("Net variance, EUR bn", L["net_variance_bn"], "0.0"),
        ("Net variance, %", L["net_variance_pct"] / 100, PCT),
        ("Variance on planned lines only, EUR bn", L["planned_lines_variance_bn"], "0.0"),
        ("Gross deviation across all budget lines, EUR bn", L["gross_line_deviation_bn"], "0.0"),
        ("Lines under-spent by > 10 % and > EUR 50 m", L["material_lines"], "0"),
        ("... their total variance, EUR bn", L["material_lines_bn"], "0.0"),
        ("Reconciliation checks passed", f"{results['checks']['passed']} of {results['checks']['total']}", "@"),
    ]
    for i, (a, b, f) in enumerate(rows):
        s.cell(4 + i, 1, a)
        s.cell(4 + i, 2, b).number_format = f
        s.cell(4 + i, 2).alignment = Alignment(horizontal="right")
    r0 = 4 + len(rows) + 1
    guide = [
        "How to use",
        "Variance: choose the year (yellow), set the materiality limits; Categories and Drivers follow.",
        "Drivers: splits the variance into planned lines, unused provisions, global savings targets and unplanned lines.",
        "Bridge: plan to actual for the largest ministries, with a chart.",
        "Top_Lines: the 50 largest line-item deviations of the latest year.",
        "Forecast: rolling backtest of year-end actuals and the outlook with an editable error band.",
        "Checks: reconciliation results; Data_* sheets hold the inputs (EUR million).",
        "Sign convention: variance = Ist - Soll. For expenses a negative variance is an under-spend.",
        f"Data downloaded {results['source']['downloaded_on']} from {results['source']['url']}; see the project README for licence and method.",
    ]
    for i, g in enumerate(guide):
        s.cell(r0 + i, 1, g).font = BOLD if i == 0 else Font()
    _widths(s, {"A": 62, "B": 16})

    wb.move_sheet("Variance", offset=-wb.index(wb["Variance"]) + 1)
    wb.save(path)
    return path
