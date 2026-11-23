"""Build main/stress query sets from Spider with executable SQLite checks."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import duckdb

from agentdb.spider import load_sqlite_tables


def load_spider_queries(parquet: str | Path, split: str = "validation") -> list[dict[str, Any]]:
    con = duckdb.connect()
    rows = con.execute(
        f"SELECT db_id, query, question FROM read_parquet('{parquet}')"
    ).fetchall()
    con.close()
    out = []
    for i, (db_id, sql, question) in enumerate(rows):
        out.append({"qid": f"{split}-{i:05d}", "db_id": db_id, "sql": sql, "question": question})
    return out


def classify_sql(sql: str) -> dict[str, bool]:
    upper = sql.upper()
    return {
        "join": " JOIN " in f" {upper} ",
        "aggregate": bool(re.search(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", upper)) or " GROUP BY " in f" {upper} ",
        "cte": upper.strip().startswith("WITH"),
        "case": " CASE " in f" {upper} ",
        "limit": " LIMIT " in f" {upper} ",
        "subquery": upper.count("SELECT") > 1,
    }


def primary_category(features: dict[str, bool]) -> str:
    if features["cte"]:
        return "cte"
    if features["case"]:
        return "case"
    if features["aggregate"]:
        return "aggregate"
    if features["join"]:
        return "join"
    return "projection"


def execute_sqlite(db_path: str | Path, sql: str, timeout_s: float = 2.0) -> tuple[int, str | None]:
    conn = sqlite3.connect(str(db_path))
    deadline = None
    try:
        conn.set_progress_handler(lambda: 1 if deadline and __import__("time").monotonic() > deadline else 0, 5000)
        import time
        deadline = time.monotonic() + timeout_s
        cur = conn.execute(sql)
        rows = cur.fetchall()
        return len(rows), None
    except Exception as exc:  # noqa: BLE001 - record execution failure
        return 0, f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()


def build_sets(
    parquet: str | Path,
    db_dir: str | Path,
    main_per_category: int = 30,
    stress_per_type: int = 8,
    max_rows: int = 30,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    queries = load_spider_queries(parquet)
    db_dir = Path(db_dir)
    tables_cache: dict[str, dict[str, Any]] = {}
    main: list[dict[str, Any]] = []
    stress: list[dict[str, Any]] = []
    counts = {"main": 0, "stress": 0, "error": 0, "empty": 0}
    main_by_cat: dict[str, int] = {}
    stress_by_type: dict[str, int] = {}

    def tables_for(db_id: str):
        if db_id not in tables_cache:
            tables_cache[db_id] = load_sqlite_tables(db_dir / f"{db_id}.sqlite", max_rows=max_rows)
        return tables_cache[db_id]

    for q in queries:
        db_path = db_dir / f"{q['db_id']}.sqlite"
        if not db_path.exists():
            counts["error"] += 1
            continue
        n_rows, err = execute_sqlite(db_path, q["sql"])
        if err:
            counts["error"] += 1
            continue
        feats = classify_sql(q["sql"])
        cat = primary_category(feats)
        base = {
            "qid": q["qid"], "db_id": q["db_id"], "sql": q["sql"], "question": q["question"],
            "category": cat, "features": feats, "n_rows": n_rows,
        }
        if n_rows > 0 and main_by_cat.get(cat, 0) < main_per_category:
            main.append(base)
            main_by_cat[cat] = main_by_cat.get(cat, 0) + 1
            counts["main"] += 1
            continue
        if n_rows == 0:
            stress_type = "empty"
        elif feats["limit"]:
            stress_type = "limit"
        elif feats["case"]:
            stress_type = "case_untriggered"
        elif feats["aggregate"]:
            stress_type = "aggregate"
        elif feats["join"] and q["sql"].upper().count(" JOIN ") >= 2:
            stress_type = "fanout"
        else:
            continue
        if stress_by_type.get(stress_type, 0) < stress_per_type:
            base["stress_type"] = stress_type
            stress.append(base)
            stress_by_type[stress_type] = stress_by_type.get(stress_type, 0) + 1
            counts["stress"] += 1
        if counts["main"] >= main_per_category * 5 and counts["stress"] >= stress_per_type * 5:
            break
    counts.update({"main_by_category": main_by_cat, "stress_by_type": stress_by_type})
    return main, stress, counts


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
