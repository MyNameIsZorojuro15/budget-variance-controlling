import numpy as np
import pandas as pd
import pytest

from bvc import calc


@pytest.fixture()
def df():
    return pd.DataFrame({"name": list("ABCDE"), "soll": [100.0, 200.0, 50.0, 0.0, 80.0],
                         "ist": [80.0, 210.0, 50.0, 5.0, 40.0]})


def test_variance_sign_and_pct(df):
    out = calc.add_variance(df)
    assert out["variance"].tolist() == [-20.0, 10.0, 0.0, 5.0, -40.0]  # Ist - Soll
    assert out.loc[0, "variance_pct"] == pytest.approx(-0.2)
    assert np.isnan(out.loc[3, "variance_pct"])  # no plan: no percentage


def test_underspent_uses_threshold_and_ignores_zero_plan(df):
    out = calc.underspent(calc.add_variance(df), 0.10)
    assert out["name"].tolist() == ["E", "A"]  # sorted by variance, most negative first
    assert calc.overspent(calc.add_variance(df), 0.04)["name"].tolist() == ["B"]


def test_decompose_adds_up_to_total_variance(df):
    d = df.assign(group=["x", "x", "y", "y", "z"])
    out = calc.decompose(d, "group")
    assert out["variance"].sum() == pytest.approx((d["ist"] - d["soll"]).sum())
    assert out["share_of_total_variance"].sum() == pytest.approx(1.0)


def test_concentration(df):
    d = calc.add_variance(df)
    assert calc.concentration(d, 1) == pytest.approx(40 / 75)
    assert calc.concentration(d, 5) == pytest.approx(1.0)


@pytest.mark.parametrize("top_n", [1, 2, 3, 10])
def test_bridge_closes_from_plan_to_actual(df, top_n):
    b = calc.bridge(df, "name", top_n=top_n)
    assert b.iloc[0]["value"] == pytest.approx(df["soll"].sum())
    assert b.iloc[-1]["value"] == pytest.approx(df["ist"].sum())
    deltas = b[b["kind"] == "delta"]
    assert b.iloc[0]["value"] + deltas["value"].sum() == pytest.approx(b.iloc[-1]["value"])
    assert deltas.iloc[-1]["end"] == pytest.approx(b.iloc[-1]["end"])  # last step lands on the actual


def test_bridge_orders_by_absolute_deviation_and_groups_the_rest(df):
    b = calc.bridge(df, "name", top_n=2)
    assert b["step"].tolist() == ["Plan (Soll)", "E", "A", "Other (3)", "Actual (Ist)"]
