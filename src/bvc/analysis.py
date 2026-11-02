"""Run the full analysis and return (results dict, frames dict). Every number in the README comes from here."""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from . import calc, checks, forecast
from .names import EP_EN, HGR_EN, localize
from .data import PROCESSED, read_meta

CRISIS_YEARS = (2020, 2021, 2022)  # pandemic and energy-crisis budgets, reported separately
PCT_THRESHOLD = 0.10               # "materially off plan": more than 10 % ...
LINE_MIN_EUR = 50e6                # ... and more than EUR 50 m on a single line
MINISTRY_MIN_PLAN = 1e9            # ministries with a plan of at least EUR 1 bn count as "large"
PLANNED_BUCKETS = ("planned_and_booked", "planned_not_booked", "renumbered")


def bn(x: float) -> float:
    return float(x) / 1e9


def analyse(con: duckdb.DuckDBPyConnection) -> tuple[dict, dict]:
    meta = read_meta()
    ep = localize(con.execute("SELECT * FROM v_variance_ep").df())
    exp_ep = ep[ep["account"] == "expenses"].copy()
    inc_ep = ep[ep["account"] == "income"].copy()
    years = sorted(exp_ep["year"].unique().tolist())
    y = int(years[-1])

    # ---- totals by year -------------------------------------------------------------------
    tot = (exp_ep.groupby("year")[["soll", "ist"]].sum().reset_index().pipe(calc.add_variance))
    gross_ep = exp_ep.assign(abs_var=exp_ep["variance"].abs()).groupby("year")["abs_var"].sum()
    tot["gross_ministry_deviation"] = tot["year"].map(gross_ep)
    inc_tot = (inc_ep.groupby("year")[["soll", "ist"]].sum().reset_index().pipe(calc.add_variance))

    # ---- latest year: ministries, categories, lines, buckets ---------------------------------
    m = exp_ep[exp_ep["year"] == y].sort_values("variance").reset_index(drop=True)
    under = calc.underspent(m, PCT_THRESHOLD)
    under_large = under[under["soll"] >= MINISTRY_MIN_PLAN]

    lines = con.execute("SELECT * FROM v_line_buckets WHERE account='expenses' AND year=?", [y]).df()
    lines = calc.add_variance(lines)
    mat = lines[(lines["soll"] > 0) & (lines["variance_pct"] < -PCT_THRESHOLD) & (lines["variance"] < -LINE_MIN_EUR)]
    gross_lines = float(lines["variance"].abs().sum())

    bk = (lines.groupby("bucket").agg(lines=("variance", "size"), soll=("soll", "sum"), ist=("ist", "sum"),
                                      variance=("variance", "sum")).reset_index())
    bk["share_of_net"] = bk["variance"] / bk["variance"].sum()
    bk_all = con.execute("SELECT * FROM v_bucket_summary WHERE account='expenses' ORDER BY year, bucket").df()
    planned_var = float(bk[bk["bucket"].isin(PLANNED_BUCKETS)]["variance"].sum())
    net_var = float(m["variance"].sum())

    cat = con.execute("""SELECT hauptgruppe, hauptgruppe_label, sum(soll) soll, sum(ist) ist, sum(variance) variance
                         FROM v_variance_category WHERE account='expenses' AND year=? GROUP BY ALL ORDER BY 1""", [y]).df()
    cat["hauptgruppe_label"] = [HGR_EN.get(("expenses", h), l) for h, l in zip(cat["hauptgruppe"], cat["hauptgruppe_label"])]
    top = localize(con.execute("SELECT * FROM v_top_lines WHERE account='expenses' AND year=? ORDER BY rnk", [y]).df())
    top_hist = localize(con.execute("""SELECT year, ep_id, ep_label, titel_label, soll, ist, variance
                              FROM v_top_lines WHERE account='expenses' AND rnk <= 5 ORDER BY year, rnk""").df())

    cat_all = localize(con.execute("SELECT * FROM v_variance_category WHERE account='expenses' ORDER BY year, ep_id, hauptgruppe").df())
    cat_all["hauptgruppe_label"] = [HGR_EN.get(("expenses", h), l) for h, l in zip(cat_all["hauptgruppe"], cat_all["hauptgruppe_label"])]
    rep = con.execute("SELECT year, quota, value FROM nodes WHERE level=0 AND account='expenses'").df()
    totals_reported = (rep.pivot(index="year", columns="quota", values="value").rename(
        columns={"target": "soll", "actual": "ist"}).reset_index())

    # ---- bridges ------------------------------------------------------------------------
    bridge_ministry = calc.bridge(m.assign(ministry=m["ep_label"]), "ministry", top_n=7)
    names = {"planned_and_booked": "Planned lines, booked", "planned_not_booked": "Planned, nothing booked",
             "savings_target": "Global savings targets", "unplanned": "Booked without plan line",
             "renumbered": "Re-numbered lines"}
    bridge_bucket = calc.bridge(bk.assign(driver=bk["bucket"].map(names)), "driver", top_n=5)

    # ---- income side -------------------------------------------------------------------------
    inc_y = inc_ep[inc_ep["year"] == y].sort_values("variance").reset_index(drop=True)

    # ---- heat map input: execution ratio for the larger ministries ----------------------------
    big = exp_ep[exp_ep["year"] == y].query("soll >= @MINISTRY_MIN_PLAN")["ep_id"]
    heat = (exp_ep[exp_ep["ep_id"].isin(big)].pivot_table(index=["ep_id", "ep_label"], columns="year",
                                                          values="variance_pct").reset_index())

    # ---- forecast -----------------------------------------------------------------------------
    hist = exp_ep[["ep_id", "year", "soll", "ist"]]
    bt = forecast.backtest(hist)
    summ_all = forecast.summarise(bt)
    summ_calm = forecast.summarise(bt, exclude_years=CRISIS_YEARS)
    outlook = pd.read_csv(PROCESSED / "outlook_soll.csv", dtype={"ep_id": str})
    out_year = int(outlook["year"].iloc[0])
    soll_out = outlook.set_index("ep_id")["soll"]
    fc_out = pd.DataFrame({"plan": forecast.forecast_year(hist, out_year, "plan", soll_out),
                           "ratio_shrunk_3": forecast.forecast_year(hist, out_year, "ratio_shrunk_3", soll_out)})
    fc_out = fc_out.join(outlook.set_index("ep_id")[["label"]]).reset_index()
    fc_out["label"] = [EP_EN.get(e, l) for e, l in zip(fc_out["ep_id"], fc_out["label"])]
    plan_err = bt[bt["method"] == "plan"]
    plan_err_calm = plan_err[~plan_err["year"].isin(CRISIS_YEARS)]
    lo, hi = float(plan_err_calm["total_error_pct"].min()), float(plan_err_calm["total_error_pct"].max())
    out_plan_total = float(soll_out.sum())

    # ---- reconciliation -----------------------------------------------------------------------
    chk = checks.run_checks(con)
    neg = checks.negative_expense_weight(con)

    # ---- results (every README number) -----------------------------------------------------
    r_y = tot[tot["year"] == y].iloc[0]
    r20 = tot[tot["year"] == 2020].iloc[0]
    results = {
        "source": {"url": meta["source"], "download_portal": meta["download_portal"],
                   "downloaded_on": meta["downloaded_on"], "years": f"{years[0]}-{years[-1]}",
                   "nodes": meta["rows"], "budget_lines_latest_year": int(len(lines))},
        "year": y,
        "latest": {
            "plan_bn": bn(r_y["soll"]), "actual_bn": bn(r_y["ist"]), "net_variance_bn": bn(net_var),
            "net_variance_pct": float(r_y["variance_pct"]) * 100,
            "gross_line_deviation_bn": bn(gross_lines),
            "planned_lines_variance_bn": bn(planned_var),
            "planned_vs_net_multiple": planned_var / net_var,
            "ministries": int(len(m)),
            "ministries_under_10pct": int(len(under)),
            "ministries_under_10pct_bn": bn(under["variance"].sum()),
            "large_ministries_under_10pct": int(len(under_large)),
            "ministries_over_plan": int((m["variance"] > 0).sum()),
            "material_lines": int(len(mat)),
            "material_lines_bn": bn(mat["variance"].sum()),
            "lines_total": int(len(lines)),
            "top20_share_of_gross": calc.concentration(lines, 20),
            "gross_ministry_deviation_bn": bn(r_y["gross_ministry_deviation"]),
            "largest_under": {"label": m.iloc[0]["ep_label"], "bn": bn(m.iloc[0]["variance"]),
                              "pct": float(m.iloc[0]["variance_pct"]) * 100},
            "second_under": {"label": m.iloc[1]["ep_label"], "bn": bn(m.iloc[1]["variance"]),
                             "pct": float(m.iloc[1]["variance_pct"]) * 100},
            "largest_over": {"label": m.iloc[-1]["ep_label"], "bn": bn(m.iloc[-1]["variance"]),
                             "pct": float(m.iloc[-1]["variance_pct"]) * 100},
            "top2_ministries_share_of_net": float(m.head(2)["variance"].sum() / net_var),
            "buckets": {r["bucket"]: {"lines": int(r["lines"]), "variance_bn": bn(r["variance"])}
                        for _, r in bk.iterrows()},
            "largest_line": {"label": top.iloc[0]["titel_label"], "ep": top.iloc[0]["ep_label"],
                             "bn": bn(top.iloc[0]["variance"])},
            "income_plan_bn": bn(inc_tot[inc_tot["year"] == y]["soll"].iloc[0]),
            "income_variance_bn": bn(inc_tot[inc_tot["year"] == y]["variance"].iloc[0]),
            "income_largest_shortfall": {"label": inc_y.iloc[0]["ep_label"], "bn": bn(inc_y.iloc[0]["variance"]),
                                         "pct": float(inc_y.iloc[0]["variance_pct"]) * 100},
        },
        "history": {
            "years_under_plan": int((tot["variance"] < 0).sum()), "years": int(len(tot)),
            "crisis_2020_variance_bn": bn(r20["variance"]), "crisis_2020_pct": float(r20["variance_pct"]) * 100,
            "avg_net_pct_ex_crisis": float(tot[~tot["year"].isin(CRISIS_YEARS)]["variance_pct"].mean()) * 100,
            "median_gross_to_net": float(
                (tot["gross_ministry_deviation"] / tot["variance"].abs()).median()),
        },
        "forecast": {
            "test_years": f"{int(bt['year'].min())}-{int(bt['year'].max())}",
            "n_test_years": int(bt["year"].nunique()),
            "wape_all": {r["method"]: float(r["mean_wape"]) * 100 for _, r in summ_all.iterrows()},
            "wape_calm": {r["method"]: float(r["mean_wape"]) * 100 for _, r in summ_calm.iterrows()},
            "total_abs_error_all": {r["method"]: float(r["mean_abs_total_error"]) * 100 for _, r in summ_all.iterrows()},
            "total_abs_error_calm": {r["method"]: float(r["mean_abs_total_error"]) * 100 for _, r in summ_calm.iterrows()},
            "best_all": summ_all.iloc[0]["method"], "best_calm": summ_calm.iloc[0]["method"],
            "plan_wape_last": float(plan_err[plan_err["year"] == y]["wape"].iloc[0]) * 100,
            "plan_total_error_last": float(plan_err[plan_err["year"] == y]["total_error_pct"].iloc[0]) * 100,
            "crisis_years": list(CRISIS_YEARS),
            "outlook_year": out_year, "outlook_plan_bn": bn(out_plan_total),
            "outlook_low_bn": bn(out_plan_total / (1 + hi)), "outlook_high_bn": bn(out_plan_total / (1 + lo)),
            "outlook_err_lo_pct": lo * 100, "outlook_err_hi_pct": hi * 100,
            "outlook_shrunk_bn": bn(fc_out["ratio_shrunk_3"].sum()),
        },
        "checks": {"passed": int((chk["result"] == "PASS").sum()), "total": int(len(chk)),
                   "negative_expense_share_actual_max_pct": float(neg[neg["quota"] == "actual"]["share_of_total"].max()) * 100},
    }
    frames = {"totals": tot, "income_totals": inc_tot, "ministries": m, "income_ministries": inc_y,
              "categories": cat, "top_lines": top, "top_lines_history": top_hist, "material_lines": mat,
              "buckets": bk, "buckets_all": bk_all, "bridge_ministry": bridge_ministry,
              "bridge_bucket": bridge_bucket, "heat": heat, "backtest": bt, "forecast_summary_all": summ_all,
              "forecast_summary_calm": summ_calm, "forecast_outlook": fc_out, "checks": chk, "negative_lines": neg,
              "ep_all": ep, "cat_all": cat_all, "totals_reported": totals_reported}
    return results, frames
