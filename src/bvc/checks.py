"""Reconciliation checks, defined as SQL views in sql/07_reconciliation.sql.

Each check returns the rows that break its rule; an empty frame is a pass.
Used by the tests, by the build (Checks sheet of the workbook) and by the README numbers.
"""
from __future__ import annotations

import duckdb
import pandas as pd

CHECKS = {
    "R1 parent value = sum of children (Einzelplan, Kapitel, Titel)": "chk_level_sums",
    "R2 line items tie to the source's category totals (Hauptgruppe)": "chk_group_totals",
    "R3 total expenses = total income (balanced budget), plan and actual": "chk_balance",
    "R4 no missing codes: every line has its parent, code prefixes match": "chk_orphans",
    "R5 no duplicate keys": "chk_duplicates",
    "R6 category code valid for the account": "chk_category_codes",
    "R7 sign check: no unexplained negative expense line above EUR 1 bn": "chk_unexplained_negative_lines",
    "R8 every year has plan and actual for expenses and income": "chk_coverage",
}


def run_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per check: name, number of violating rows, PASS/FAIL."""
    rows = []
    for name, view in CHECKS.items():
        n = con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        rows.append({"check": name, "violations": int(n), "result": "PASS" if n == 0 else "FAIL"})
    return pd.DataFrame(rows)


def negative_expense_weight(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """R8 sign check: negative expense lines (refunds, negative reserves) by year and their weight on actuals."""
    return con.execute("""
        WITH neg AS (SELECT year, quota, count(*) AS lines, sum(value) AS negative_total
                     FROM chk_negative_expense_lines GROUP BY ALL),
             tot AS (SELECT year, quota, value AS total FROM nodes WHERE level = 0 AND account = 'expenses')
        SELECT t.year, t.quota, coalesce(n.lines, 0) AS lines, coalesce(n.negative_total, 0) AS negative_total,
               abs(coalesce(n.negative_total, 0)) / t.total AS share_of_total
        FROM tot t LEFT JOIN neg n USING (year, quota) ORDER BY 1, 2""").df()
