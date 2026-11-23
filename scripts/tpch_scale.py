"""TPC-H real-value scale control at SF0.1 (600k lineitem rows).

The script runs the same six hand-specified control queries used for the
SF0.001/SF0.01 control, but executes directly against the on-disk SQLite
database so the full 600k-row instance is probed.  It reports edge recovery
and wall-clock latency for cell-only and literal probing.

This is a scale control, not a new human-annotated benchmark.  The eight
control edges are the same hand-specified edges used in the small control.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from agentdb.sqlite_oracle import (
    _apply_cell,
    _candidate_values,
    _changed_outputs,
    _rollback,
    _rowids,
    _run,
    _savepoint,
    sql_literals,
)

QUERIES = [
    ("q1", "SELECT c_name FROM customer WHERE c_nationkey = 1",
     {("c_name", "customer", "c_nationkey")}),
    ("q2", "SELECT c_name FROM customer WHERE c_mktsegment = 'BUILDING'",
     {("c_name", "customer", "c_mktsegment")}),
    ("q3", "SELECT o_orderkey, o_totalprice FROM orders WHERE o_orderdate >= '1995-01-01'",
     {("o_orderkey", "orders", "o_orderdate"), ("o_totalprice", "orders", "o_orderdate")}),
    ("q4", "SELECT SUM(l_quantity) FROM lineitem WHERE l_shipdate >= '1995-01-01' AND l_partkey = 1",
     {("sum(l_quantity)", "lineitem", "l_shipdate"), ("sum(l_quantity)", "lineitem", "l_partkey")}),
    ("q5", "SELECT s_name FROM supplier WHERE s_acctbal > 5000",
     {("s_name", "supplier", "s_acctbal")}),
    ("q6", "SELECT p_name FROM part WHERE p_size = 15",
     {("p_name", "part", "p_size")}),
]


def norm(edges):
    return {(str(o).casefold().strip(), str(t).casefold().strip(), str(c).casefold().strip())
            for o, t, c in edges}


def table_columns(conn: sqlite3.Connection):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    out = []
    for table in tables:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        out.append((table, [(row[1], row[2]) for row in info]))
    return out


def probe(conn: sqlite3.Connection, sql: str, mode: str, budget: int,
          max_candidates: int, timeout_s: float) -> tuple[set, int, float]:
    """Probe the on-disk DB and return (edges, executions, seconds)."""
    start = time.perf_counter()
    base = _run(conn, sql, timeout_s)
    literals = sql_literals(sql)
    import random
    rng = random.Random(42)
    edges = set()
    executions = 0
    for table, cols in table_columns(conn):
        rowids = _rowids(conn, table)[:budget]
        for col, sql_type in cols:
            if mode == "cell":
                candidates = [None]  # sentinel: use the cell-value bump
            else:
                candidates = _candidate_values(sql_type, literals, mode="full", rng=rng)[:max_candidates]
            for rowid in rowids:
                old_value = conn.execute(
                    f'SELECT "{col}" FROM "{table}" WHERE rowid = ?', (rowid,)
                ).fetchone()[0]
                for cand in candidates:
                    _savepoint(conn)
                    try:
                        if mode == "cell":
                            if not _apply_cell(conn, table, col, rowid, "CELL_VALUE", sql_type, old_value):
                                continue
                        else:
                            if cand == old_value:
                                continue
                            conn.execute(
                                f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (cand, rowid)
                            )
                        perturbed = _run(conn, sql, timeout_s)
                        executions += 1
                        for out in _changed_outputs(base, perturbed):
                            edges.add((out, table.casefold(), col.casefold()))
                    finally:
                        _rollback(conn)
    return edges, executions, time.perf_counter() - start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tpch_sf01.sqlite")
    ap.add_argument("--out", default="results/tpch_scale.json")
    ap.add_argument("--budget", type=int, default=3)
    ap.add_argument("--max-candidates", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"missing database: {db}")
    conn = sqlite3.connect(str(db))
    try:
        n_lineitem = conn.execute("SELECT COUNT(*) FROM lineitem").fetchone()[0]
        rows = []
        for qid, sql, expected in QUERIES:
            expected = {(o.casefold(), t.casefold(), c.casefold()) for o, t, c in expected}
            cell, cell_exec, cell_s = probe(conn, sql, "cell", args.budget,
                                            args.max_candidates, args.timeout)
            lit, lit_exec, lit_s = probe(conn, sql, "literal", args.budget,
                                         args.max_candidates, args.timeout)
            rows.append({
                "qid": qid,
                "sql": sql,
                "expected_control": sorted(expected),
                "cell_recovered": sorted(expected & cell),
                "literal_recovered": sorted(expected & lit),
                "cell_recall": len(expected & cell) / len(expected),
                "literal_recall": len(expected & lit) / len(expected),
                "cell_executions": cell_exec,
                "literal_executions": lit_exec,
                "cell_seconds": round(cell_s, 3),
                "literal_seconds": round(lit_s, 3),
            })
            print(json.dumps(rows[-1], ensure_ascii=False))
    finally:
        conn.close()

    payload = {
        "db": str(db),
        "lineitem_rows": n_lineitem,
        "budget": args.budget,
        "max_candidates": args.max_candidates,
        "queries": rows,
        "summary": {
            "cell_recovered": sum(len(r["cell_recovered"]) for r in rows),
            "literal_recovered": sum(len(r["literal_recovered"]) for r in rows),
            "n_expected": sum(len(r["expected_control"]) for r in rows),
            "cell_seconds_mean": sum(r["cell_seconds"] for r in rows) / len(rows),
            "literal_seconds_mean": sum(r["literal_seconds"] for r in rows) / len(rows),
            "cell_executions_mean": sum(r["cell_executions"] for r in rows) / len(rows),
            "literal_executions_mean": sum(r["literal_executions"] for r in rows) / len(rows),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
