"""Load the downloaded budget into DuckDB and build the analysis views from sql/."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"


def read_meta(processed: Path = PROCESSED) -> dict:
    return json.loads((processed / "download_meta.json").read_text(encoding="utf-8"))


def load_frames(processed: Path = PROCESSED) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(processed / "nodes.csv.gz", dtype={"id": str, "parent_id": str, "budget_number": str})
    nodes["parent_id"] = nodes["parent_id"].fillna("")
    groups = pd.read_csv(processed / "group_totals.csv", dtype={"group_id": str})
    return nodes, groups


def connect(processed: Path = PROCESSED, nodes: pd.DataFrame | None = None,
            groups: pd.DataFrame | None = None) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with tables `nodes`, `group_totals`, `fact_titel` and all views from sql/.

    `nodes` / `groups` can be passed in (the tests use this to inject deliberately broken data).
    """
    if nodes is None or groups is None:
        n0, g0 = load_frames(processed)
        nodes = n0 if nodes is None else nodes
        groups = g0 if groups is None else groups
    con = duckdb.connect()
    con.register("nodes_df", nodes)
    con.register("groups_df", groups)
    con.execute("CREATE TABLE nodes AS SELECT * FROM nodes_df")
    con.execute("CREATE TABLE group_totals AS SELECT * FROM groups_df")
    for path in sorted(SQL_DIR.glob("*.sql")):
        con.execute(path.read_text(encoding="utf-8"))
    return con
