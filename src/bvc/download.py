"""Download the German federal budget (Soll = plan, Ist = actual) from bundeshaushalt.de.

Source: the public JSON interface behind https://www.bundeshaushalt.de (Federal Ministry of Finance).
For every year, quota (target/actual) and account (expenses/income) the script walks the plan hierarchy
Einzelplan (ministry) -> Kapitel (chapter) -> Titel (line item) and writes one tidy table, plus the
Hauptgruppe (economic category) totals, which are used later as an independent cross-check.

Raw responses are cached in data/raw/cache (git-ignored), so an interrupted run resumes where it stopped.

    python -m bvc.download            # all years 2012-2025
    python -m bvc.download --years 2023 2024
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

API = "https://www.bundeshaushalt.de/internalapi/"
PORTAL = "https://www.bundeshaushalt.de/DE/Download-Portal/download-portal.html"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "cache"
PROCESSED = ROOT / "data" / "processed"

YEARS = list(range(2012, 2026))  # Ist (actual) is published for 2012-2025
QUOTAS = ("target", "actual")  # Soll, Ist
ACCOUNTS = ("expenses", "income")
USER_AGENT = "budget-variance-controlling/0.1 (portfolio project; polite crawler)"


def fetch(params: dict, retries: int = 5) -> dict:
    """GET one budgetData response, cached on disk."""
    key = "_".join(f"{k}-{params[k]}" for k in ("year", "quota", "account", "unit", "id"))
    path = CACHE / f"{key or 'root'}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    url = API + "budgetData?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            path.write_text(body, encoding="utf-8")
            return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed after {retries} tries: {url}")


def _q(year: int, quota: str, account: str, unit: str, id_: str = "") -> dict:
    return {"year": year, "quota": quota, "account": account, "unit": unit, "id": id_}


def crawl_one(year: int, quota: str, account: str) -> list[dict]:
    """All nodes of one (year, quota, account) tree: level 0 total, 1 Einzelplan, 2 Kapitel, 3 Titel."""
    rows: list[dict] = []
    root = fetch(_q(year, quota, account, "single"))
    modified = root["meta"].get("modifyDate")
    rows.append({"year": year, "quota": quota, "account": account, "level": 0, "id": "TOTAL",
                 "parent_id": "", "budget_number": "", "label": root["detail"].get("label", ""),
                 "value": root["detail"].get("value", 0.0), "source_modified": modified})

    def add(children, level, parent, meta):
        for c in children:
            rows.append({"year": year, "quota": quota, "account": account, "level": level,
                         "id": c["id"], "parent_id": parent, "budget_number": c["budgetNumber"],
                         "label": c["label"], "value": c["value"],
                         "source_modified": meta.get("modifyDate")})

    add(root.get("children", []), 1, "TOTAL", root["meta"])
    for ep in [c["id"] for c in root.get("children", [])]:
        d = fetch(_q(year, quota, account, "single", ep))
        add(d.get("children", []), 2, ep, d["meta"])
        for kap in [c["id"] for c in d.get("children", [])]:
            k = fetch(_q(year, quota, account, "single", kap))
            add(k.get("children", []), 3, kap, k["meta"])
    return rows


def crawl_groups(year: int, quota: str, account: str) -> list[dict]:
    """Totals per Hauptgruppe (economic category), straight from the source's own group view."""
    d = fetch(_q(year, quota, account, "group"))
    return [{"year": year, "quota": quota, "account": account, "group_id": c["id"],
             "label": c["label"], "value": c["value"]} for c in d.get("children", [])]


OUTLOOK_YEAR = 2026  # adopted plan for the year after the last published actuals


def crawl_outlook(year: int = OUTLOOK_YEAR) -> list[dict]:
    """Plan (Soll) per ministry for a year without actuals yet; the input of the forward forecast."""
    root = fetch(_q(year, "target", "expenses", "single"))
    return [{"year": year, "ep_id": c["id"], "label": c["label"], "soll": c["value"],
             "source_modified": root["meta"].get("modifyDate")} for c in root.get("children", [])]


def main(years=None, workers: int = 8) -> None:
    years = years or YEARS
    CACHE.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    jobs = [(y, q, a) for y in years for q in QUOTAS for a in ACCOUNTS]
    nodes, groups = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for rows in pool.map(lambda j: crawl_one(*j), jobs):
            nodes.extend(rows)
        for rows in pool.map(lambda j: crawl_groups(*j), jobs):
            groups.extend(rows)
    df = pd.DataFrame(nodes).sort_values(["account", "year", "quota", "level", "id"])
    df.to_csv(PROCESSED / "nodes.csv.gz", index=False, compression="gzip")
    pd.DataFrame(groups).sort_values(["account", "year", "quota", "group_id"]).to_csv(
        PROCESSED / "group_totals.csv", index=False)
    pd.DataFrame(crawl_outlook()).to_csv(PROCESSED / "outlook_soll.csv", index=False)
    meta = {"source": "https://www.bundeshaushalt.de", "api": API, "download_portal": PORTAL,
            "downloaded_on": date.today().isoformat(), "years": years, "rows": int(len(df))}
    (PROCESSED / "download_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"{len(df):,} nodes, {len(groups):,} group rows -> {PROCESSED}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    main(a.years, a.workers)
