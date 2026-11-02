import pandas as pd
import pytest

from bvc import forecast as F


def hist(ratios):
    """Two ministries; A executes at `ratios[year]` of plan, B exactly at plan."""
    rows = []
    for y, r in ratios.items():
        rows.append({"ep_id": "A", "year": y, "soll": 100.0, "ist": 100.0 * r})
        rows.append({"ep_id": "B", "year": y, "soll": 50.0, "ist": 50.0})
    return pd.DataFrame(rows)


def test_plan_method_returns_the_plan():
    h = hist({2018: 0.9, 2019: 0.9, 2020: 0.9})
    assert F.forecast_year(h, 2020, "plan").to_dict() == {"A": 100.0, "B": 50.0}


def test_ratio_method_is_exact_when_the_ratio_is_stable():
    h = hist({2016: 0.9, 2017: 0.9, 2018: 0.9, 2019: 0.9})
    f = F.forecast_year(h, 2019, "ratio_mean_3")
    assert f["A"] == pytest.approx(90.0) and f["B"] == pytest.approx(50.0)


def test_shrunk_ratio_is_halfway():
    h = hist({2016: 0.8, 2017: 0.8, 2018: 0.8, 2019: 0.8})
    assert F.forecast_year(h, 2019, "ratio_shrunk_3")["A"] == pytest.approx(90.0)


def test_last_actual():
    h = hist({2018: 0.7, 2019: 0.9})
    assert F.forecast_year(h, 2019, "last_actual")["A"] == pytest.approx(70.0)


def test_no_look_ahead_future_actuals_do_not_change_the_forecast():
    base = hist({2016: 0.9, 2017: 0.95, 2018: 1.0, 2019: 1.1})
    changed = base.copy()
    changed.loc[(changed["year"] >= 2019) & (changed["ep_id"] == "A"), "ist"] = 1.0  # rewrite the year being forecast
    extra = pd.concat([changed, pd.DataFrame([{"ep_id": "A", "year": 2021, "soll": 100.0, "ist": 5.0}])])
    for m in F.METHODS:
        assert F.forecast_year(base, 2019, m).equals(F.forecast_year(extra, 2019, m)), m


def test_wape():
    a = pd.Series({"A": 100.0, "B": 100.0})
    f = pd.Series({"A": 90.0, "B": 110.0})
    assert F.wape(f, a) == pytest.approx(0.10)


def test_backtest_scores_methods_on_the_same_ministries_and_years():
    h = hist({y: 0.95 for y in range(2012, 2020)})
    bt = F.backtest(h, methods=("plan", "ratio_mean_3"))
    assert sorted(bt["year"].unique()) == [2015, 2016, 2017, 2018, 2019]  # needs 3 years of history
    assert bt.groupby("year")["ministries"].nunique().max() == 1
    plan = bt[bt["method"] == "plan"]["wape"].iloc[0]
    assert plan == pytest.approx(5.0 / 145.0)  # A is 5 over plan, total actual 145


def test_summarise_excludes_requested_years():
    h = hist({y: 0.95 for y in range(2012, 2020)})
    bt = F.backtest(h, methods=("plan",))
    assert F.summarise(bt, exclude_years=(2019,))["years"].iloc[0] == 4
