"""The reconciliation checks: they pass on the official data and each one fails on deliberately broken data."""
import pandas as pd
import pytest

from bvc.checks import CHECKS, run_checks
from bvc.data import connect


def violations(con, view):
    return con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]


def test_all_checks_pass_on_real_data(con):
    res = run_checks(con)
    assert len(res) == len(CHECKS) == 8
    assert (res["result"] == "PASS").all(), res[res["result"] == "FAIL"]


def test_real_data_covers_all_years_and_both_quotas(con):
    n = con.execute("SELECT count(DISTINCT year), count(DISTINCT quota), count(DISTINCT account) FROM nodes").fetchone()
    assert n == (14, 2, 2)


def test_negative_expense_lines_are_small_and_explained(con):
    from bvc.checks import negative_expense_weight

    neg = negative_expense_weight(con)
    assert neg[neg["quota"] == "actual"]["share_of_total"].max() < 0.03


def _first(df, **kw):
    mask = pd.Series(True, index=df.index)
    for k, v in kw.items():
        mask &= df[k] == v
    return df[mask].index[0]


def test_r1_catches_a_changed_line_value(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=3, year=2024, quota="actual", account="expenses")
    nodes.loc[i, "value"] += 1_000_000
    assert violations(connect(nodes=nodes, groups=groups), "chk_level_sums") == 1  # the chapter no longer ties to its lines


def test_r2_catches_a_category_total_that_does_not_tie(raw_frames):
    nodes, groups = raw_frames
    groups.loc[0, "value"] += 5_000
    assert violations(connect(nodes=nodes, groups=groups), "chk_group_totals") == 1


def test_r3_catches_an_unbalanced_budget(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=0, year=2023, quota="target", account="income")
    nodes.loc[i, "value"] -= 10_000_000
    assert violations(connect(nodes=nodes, groups=groups), "chk_balance") == 1


def test_r4_catches_a_missing_chapter(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=2, year=2022, quota="actual", account="expenses")
    nodes = nodes.drop(i)
    assert violations(connect(nodes=nodes, groups=groups), "chk_orphans") > 0


def test_r4_catches_a_malformed_code(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=3, year=2022, quota="actual", account="expenses")
    nodes.loc[i, "id"] = nodes.loc[i, "id"][:-1]
    assert violations(connect(nodes=nodes, groups=groups), "chk_orphans") >= 1


def test_r5_catches_a_duplicate_key(raw_frames):
    nodes, groups = raw_frames
    nodes = pd.concat([nodes, nodes.iloc[[1000]]], ignore_index=True)
    assert violations(connect(nodes=nodes, groups=groups), "chk_duplicates") == 1


def test_r6_catches_an_invalid_category_digit(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=3, year=2021, quota="target", account="expenses")
    old = nodes.loc[i, "id"]
    nodes.loc[i, "id"] = old[:4] + "1" + old[5:]
    assert violations(connect(nodes=nodes, groups=groups), "chk_category_codes") == 1


def test_r7_catches_an_unexplained_large_negative_expense_line(raw_frames):
    nodes, groups = raw_frames
    i = _first(nodes, level=3, year=2021, quota="actual", account="expenses")
    nodes.loc[i, "value"] = -3e9
    nodes.loc[i, "label"] = "0000 000 00 Unknown item"
    assert violations(connect(nodes=nodes, groups=groups), "chk_unexplained_negative_lines") == 1


def test_r8_catches_a_missing_year_and_quota(raw_frames):
    nodes, groups = raw_frames
    nodes = nodes[~((nodes["year"] == 2019) & (nodes["quota"] == "actual") & (nodes["account"] == "income"))]
    assert violations(connect(nodes=nodes, groups=groups), "chk_coverage") == 1
