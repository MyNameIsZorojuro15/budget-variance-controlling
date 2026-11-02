"""The SQL layer: facts tie to the source totals and the driver buckets add up."""
import pandas as pd
import pytest

from bvc.data import connect


def node(level, id_, parent, value, label="x", year=2024, quota="target", account="expenses"):
    return {"year": year, "quota": quota, "account": account, "level": level, "id": id_, "parent_id": parent,
            "budget_number": "", "label": label, "value": value, "source_modified": "01.01.2025"}


def tiny():
    """One ministry, one chapter. Lines: booked, not booked, unplanned, savings target, a moved (re-numbered) line."""
    rows = [node(1, "01", "TOTAL", 0, "01 Ministry")]
    rows += [node(1, "01", "TOTAL", 0, "01 Ministry", quota="actual")]
    plan = {"010142101": ("Salaries", 100), "010152901": ("Unused provision", 40), "010169999": ("Global saving", -30),
            "010182001": ("Moved item", 25)}
    act = {"010142101": ("Salaries", 90), "010163001": ("Carry-over use", 12), "010182009": ("Moved item", 20)}
    for q, d in (("target", plan), ("actual", act)):
        for id_, (label, v) in d.items():
            rows.append(node(3, id_, "0101", float(v), f"0101 000 00 {label}", quota=q))
    groups = pd.DataFrame([{"year": 2024, "quota": "target", "account": "expenses", "group_id": "G-4", "label": "4 x",
                            "value": 0.0}])
    return pd.DataFrame(rows), groups


def test_bucket_classification_on_a_small_example():
    nodes, groups = tiny()
    con = connect(nodes=nodes, groups=groups)
    b = dict(con.execute("SELECT titel_id, bucket FROM v_line_buckets").fetchall())
    assert b == {"010142101": "planned_and_booked", "010152901": "planned_not_booked",
                 "010169999": "savings_target", "010163001": "unplanned",
                 "010182001": "renumbered", "010182009": "renumbered"}


def test_bucket_variances_add_up_on_the_small_example():
    nodes, groups = tiny()
    con = connect(nodes=nodes, groups=groups)
    total = con.execute("SELECT sum(variance) FROM v_line_buckets").fetchone()[0]
    assert total == pytest.approx((90 + 12 + 20) - (100 + 40 - 30 + 25))
    by = dict(con.execute("SELECT bucket, sum(variance) FROM v_line_buckets GROUP BY 1").fetchall())
    assert by["savings_target"] == 30 and by["planned_not_booked"] == -40 and by["renumbered"] == -5


def test_fact_titel_totals_equal_the_source_totals(con):
    """Per year: sum of lines = reported total, for plan and actual, expenses and income."""
    q = con.execute("""
        SELECT f.account, f.year, sum(f.soll) - max(t.soll) AS d_soll, sum(f.ist) - max(t.ist) AS d_ist
        FROM fact_titel f
        JOIN (SELECT account, year,
                     max(value) FILTER (WHERE quota = 'target') AS soll,
                     max(value) FILTER (WHERE quota = 'actual') AS ist
              FROM nodes WHERE level = 0 GROUP BY 1, 2) t USING (account, year)
        GROUP BY f.account, f.year""").df()
    assert q["d_soll"].abs().max() < 1.0 and q["d_ist"].abs().max() < 1.0


def test_every_year_buckets_add_up_to_total_variance(con):
    q = con.execute("""
        SELECT b.year, b.v - e.v AS diff
        FROM (SELECT year, sum(variance) v FROM v_bucket_summary WHERE account = 'expenses' GROUP BY 1) b
        JOIN (SELECT year, sum(variance) v FROM v_variance_ep WHERE account = 'expenses' GROUP BY 1) e USING (year)""").df()
    assert len(q) == 14 and q["diff"].abs().max() < 1.0


def test_each_line_is_in_exactly_one_bucket(con):
    n_lines, n_fact = con.execute("SELECT (SELECT count(*) FROM v_line_buckets), (SELECT count(*) FROM fact_titel)").fetchone()
    assert n_lines == n_fact


def test_ministry_and_category_views_agree(con):
    d = con.execute("""
        SELECT abs(sum(e.variance) - sum(c.variance)) FROM
          (SELECT sum(variance) variance FROM v_variance_ep WHERE account='expenses') e,
          (SELECT sum(variance) variance FROM v_variance_category WHERE account='expenses') c""").fetchone()[0]
    assert d < 1.0
