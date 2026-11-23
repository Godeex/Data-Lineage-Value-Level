"""External control comparison on the six TPC-H control queries.

Reports CONTROL and DATA recovery for static parsing, ProvSQL where-
provenance, cell-only probing, literal probing, and Static+Literal.  The
DATA edges are the projected/aggregate self-edges; the CONTROL edges are the
hand-specified predicate dependencies used in the paper.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agentdb.data import schema_for
from agentdb.lineage import extract_static_lineage
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

DB = Path("data/tpch_control.sqlite")
QUERIES = [
    ("q1", "SELECT c_name FROM customer WHERE c_nationkey = 1",
     {("c_name", "customer", "c_nationkey")}, {("c_name", "customer", "c_name")}),
    ("q2", "SELECT c_name FROM customer WHERE c_mktsegment = 'BUILDING'",
     {("c_name", "customer", "c_mktsegment")}, {("c_name", "customer", "c_name")}),
    ("q3", "SELECT o_orderkey, o_totalprice FROM orders WHERE o_orderdate >= '1995-01-01'",
     {("o_orderkey", "orders", "o_orderdate"), ("o_totalprice", "orders", "o_orderdate")},
     {("o_orderkey", "orders", "o_orderkey"), ("o_totalprice", "orders", "o_totalprice")}),
    ("q4", "SELECT SUM(l_quantity) FROM lineitem WHERE l_shipdate >= '1995-01-01' AND l_partkey = 1",
     {("sum(l_quantity)", "lineitem", "l_shipdate"), ("sum(l_quantity)", "lineitem", "l_partkey")},
     {("sum(l_quantity)", "lineitem", "l_quantity")}),
    ("q5", "SELECT s_name FROM supplier WHERE s_acctbal > 5000",
     {("s_name", "supplier", "s_acctbal")}, {("s_name", "supplier", "s_name")}),
    ("q6", "SELECT p_name FROM part WHERE p_size = 15",
     {("p_name", "part", "p_size")}, {("p_name", "part", "p_name")}),
]


def norm(edges, names):
    import re
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        m = re.fullmatch(r"_col_(\d+)", o)
        if m and int(m.group(1)) < len(names):
            o = names[int(m.group(1))]
        out.add((o, str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def output_names(sql: str) -> list[str]:
    conn = sqlite3.connect(str(DB))
    try:
        return [str(d[0]).casefold().strip() for d in (conn.execute(sql).description or [])]
    except Exception:
        return []
    finally:
        conn.close()


def main() -> int:
    tables = load_sqlite_tables(DB, max_rows=10000)
    schema = schema_for({"tables": tables})
    rows = []
    totals = {name: {"control": 0, "data": 0} for name in
              ("Static", "ProvSQL", "Cell-only", "Literal", "Static+Literal")}
    provsql = {r["qid"]: r for r in json.loads(Path("results/provsql_tpch.json").read_text())["queries"]}
    for qid, sql, control, data in QUERIES:
        names = output_names(sql)
        script = {"sql": sql, "tables": tables}
        static = norm(extract_static_lineage(sql, schema, dialect="sqlite"), names)
        cell = norm(limited_edges(script, ["CELL_VALUE"], 3)["edges"], names)
        lit = norm(literal_edges(script, budget=3)["edges"], names)
        union = static | lit
        prov = {tuple(e) for e in provsql[qid]["recovered_edges"]}
        values = {
            "Static": static,
            "ProvSQL": prov,
            "Cell-only": cell,
            "Literal": lit,
            "Static+Literal": union,
        }
        item = {"qid": qid, "control_edges": sorted(control), "data_edges": sorted(data)}
        for name, edges in values.items():
            c = len(control & edges)
            d = len(data & edges)
            item[name] = {"control": c, "data": d}
            totals[name]["control"] += c
            totals[name]["data"] += d
        rows.append(item)

    payload = {
        "n_control": sum(len(q[2]) for q in QUERIES),
        "n_data": sum(len(q[3]) for q in QUERIES),
        "summary": totals,
        "queries": rows,
        "note": "ProvSQL q4 aggregate where-provenance is unsupported; its DATA denominator is 7.",
    }
    Path("results/tpch_external.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
