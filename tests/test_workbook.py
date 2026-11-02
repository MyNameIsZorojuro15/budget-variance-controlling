"""The workbook: structure, and its formulas recalculated by an independent engine equal the Python results."""
import pytest
from openpyxl import load_workbook

from bvc.data import ROOT

XLSX = ROOT / "reports" / "budget_variance_workbook.xlsx"


def test_sheets_and_inputs_exist():
    wb = load_workbook(XLSX)
    for name in ("Summary", "Variance", "Categories", "Drivers", "Bridge", "Top_Lines", "Forecast", "Checks",
                 "Data_EP", "Data_Cat", "Data_Bucket", "Data_Totals"):
        assert name in wb.sheetnames
    v = wb["Variance"]
    assert v["C3"].value == 2025 and v["C4"].value == 0.10 and v["C5"].value == 100
    assert v["E8"].value.startswith("=")  # formulas, not pasted values
    assert wb["Bridge"]._charts, "bridge chart missing"


def test_formulas_recalculate_to_the_python_numbers(analysis, tmp_path):
    import formulas

    results, frames = analysis
    xl = formulas.ExcelModel().loads(str(XLSX)).finish()
    sol = xl.calculate()

    def val(sheet, cell):
        v = sol[f"'[{XLSX.name}]{sheet.upper()}'!{cell}"].value
        return v[0, 0]

    wb = load_workbook(XLSX)
    ws = wb["Variance"]
    last = next(r for r in range(8, 80) if ws.cell(r, 2).value == "Total")
    L = results["latest"]
    assert val("Variance", f"C{last}") / 1e3 == pytest.approx(L["plan_bn"], rel=1e-9)
    assert val("Variance", f"D{last}") / 1e3 == pytest.approx(L["actual_bn"], rel=1e-9)
    assert val("Variance", f"E{last}") / 1e3 == pytest.approx(L["net_variance_bn"], rel=1e-6)
    assert val("Variance", f"C{last + 3}") == pytest.approx(0, abs=1e-3)  # ministries tie to the reported total
    assert val("Drivers", "F11") / 1e3 == pytest.approx(L["net_variance_bn"], rel=1e-6)
    assert val("Drivers", "F12") / 1e3 == pytest.approx(L["planned_lines_variance_bn"], rel=1e-6)
    assert val("Drivers", "F14") == pytest.approx(0, abs=1e-3)

    def row_of(sheet, text, col):
        w = wb[sheet]
        return next(r for r in range(1, w.max_row + 1) if str(w.cell(r, col).value or "").startswith(text))

    r = row_of("Categories", "Difference to Variance", 2)
    assert val("Categories", f"E{r}") == pytest.approx(0, abs=1e-3)
    r = row_of("Bridge", "Check: plan + steps", 1)
    assert val("Bridge", f"C{r}") == pytest.approx(0, abs=1e-3)
    r = row_of("Checks", "All live checks zero?", 1)
    assert val("Checks", f"B{r}") == "PASS"
