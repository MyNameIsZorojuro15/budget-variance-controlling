"""Headline numbers are reproduced independently, and the README is generated from them."""
import json
from pathlib import Path

import pytest

from bvc import readme
from bvc.data import ROOT

REPORTS = ROOT / "reports"


def assert_same(a, b, path="results"):
    """Recursive comparison: numbers to 1e-9 (float summation order), everything else exactly."""
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            assert_same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            assert_same(x, y, f"{path}[{i}]")
    elif isinstance(a, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), path
    else:
        assert a == b, path


def test_headline_matches_an_independent_calculation_from_the_source_totals(con, analysis):
    results, _ = analysis
    y = results["year"]
    soll, ist = con.execute("""SELECT max(value) FILTER (WHERE quota='target'), max(value) FILTER (WHERE quota='actual')
                               FROM nodes WHERE level = 0 AND account = 'expenses' AND year = ?""", [y]).fetchone()
    L = results["latest"]
    assert L["plan_bn"] == pytest.approx(soll / 1e9)
    assert L["actual_bn"] == pytest.approx(ist / 1e9)
    assert L["net_variance_bn"] == pytest.approx((ist - soll) / 1e9, abs=1e-6)


def test_buckets_add_up_to_the_headline(analysis):
    L = analysis[0]["latest"]
    assert sum(v["variance_bn"] for v in L["buckets"].values()) == pytest.approx(L["net_variance_bn"], abs=1e-6)
    planned = sum(L["buckets"][k]["variance_bn"] for k in ("planned_and_booked", "planned_not_booked", "renumbered"))
    assert planned == pytest.approx(L["planned_lines_variance_bn"])
    assert L["planned_vs_net_multiple"] == pytest.approx(planned / L["net_variance_bn"])


def test_material_lines_respect_both_limits(analysis):
    results, frames = analysis
    m = frames["material_lines"]
    assert len(m) == results["latest"]["material_lines"]
    assert ((m["variance"] / m["soll"]) < -0.10).all() and (m["variance"] < -50e6).all()


def test_all_reconciliation_checks_pass_in_results(analysis):
    c = analysis[0]["checks"]
    assert c["passed"] == c["total"] == 8


def test_forecast_backtest_is_ordered_and_sane(analysis):
    f = analysis[0]["forecast"]
    assert f["n_test_years"] == 11
    assert f["wape_all"]["last_actual"] > f["wape_all"]["plan"]  # naive last-year is worse than the budget
    assert f["outlook_low_bn"] < f["outlook_plan_bn"] < f["outlook_high_bn"] or f["outlook_err_lo_pct"] < 0


def test_results_json_on_disk_matches_a_fresh_run(analysis):
    on_disk = json.loads((REPORTS / "results.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(analysis[0], default=str))
    assert_same(on_disk, fresh)


def test_readme_is_exactly_what_the_code_renders(analysis):
    results, frames = analysis
    assert (ROOT / "README.md").read_text(encoding="utf-8") == readme.render(results, frames)


def test_project_has_no_tool_or_personal_references():
    banned = ("claude", "anthropic", "ai agent", "llm", "gpt", "copilot", "freire")
    for path in ROOT.rglob("*"):
        if (not path.is_file() or any(p in path.parts for p in (".venv", "raw", ".pytest_cache", "__pycache__"))
                or path.suffix in {".png", ".xlsx", ".gz", ".pyc"} or path.name == "test_results.py"
                or ".egg-info" in str(path)):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert not any(b in text for b in banned), f"{path} mentions one of {banned}"
