"""Run ProvSQL where-provenance on the TPC-H control queries.

ProvSQL is an external provenance engine, not a perturbation oracle.  It
returns the source cell of each projected value.  This script records what it
recovers on the same six control queries used by the paper: self/projection
DATA edges are expected, predicate CONTROL edges are not.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import subprocess
from pathlib import Path

TABLES = {
    "region": [("r_regionkey", "BIGINT"), ("r_name", "VARCHAR"), ("r_comment", "VARCHAR")],
    "nation": [("n_nationkey", "BIGINT"), ("n_name", "VARCHAR"), ("n_regionkey", "BIGINT"), ("n_comment", "VARCHAR")],
    "customer": [("c_custkey", "BIGINT"), ("c_name", "VARCHAR"), ("c_address", "VARCHAR"),
                 ("c_nationkey", "BIGINT"), ("c_phone", "VARCHAR"), ("c_acctbal", "NUMERIC"),
                 ("c_mktsegment", "VARCHAR"), ("c_comment", "VARCHAR")],
    "supplier": [("s_suppkey", "BIGINT"), ("s_name", "VARCHAR"), ("s_address", "VARCHAR"),
                 ("s_nationkey", "BIGINT"), ("s_phone", "VARCHAR"), ("s_acctbal", "NUMERIC"),
                 ("s_comment", "VARCHAR")],
    "part": [("p_partkey", "BIGINT"), ("p_name", "VARCHAR"), ("p_mfgr", "VARCHAR"),
             ("p_brand", "VARCHAR"), ("p_type", "VARCHAR"), ("p_size", "BIGINT"),
             ("p_container", "VARCHAR"), ("p_retailprice", "NUMERIC"), ("p_comment", "VARCHAR")],
    "partsupp": [("ps_partkey", "BIGINT"), ("ps_suppkey", "BIGINT"), ("ps_availqty", "BIGINT"),
                 ("ps_supplycost", "NUMERIC"), ("ps_comment", "VARCHAR")],
    "orders": [("o_orderkey", "BIGINT"), ("o_custkey", "BIGINT"), ("o_orderstatus", "VARCHAR"),
               ("o_totalprice", "NUMERIC"), ("o_orderdate", "DATE"), ("o_orderpriority", "VARCHAR"),
               ("o_clerk", "VARCHAR"), ("o_shippriority", "BIGINT"), ("o_comment", "VARCHAR")],
    "lineitem": [("l_orderkey", "BIGINT"), ("l_partkey", "BIGINT"), ("l_suppkey", "BIGINT"),
                 ("l_linenumber", "BIGINT"), ("l_quantity", "NUMERIC"), ("l_extendedprice", "NUMERIC"),
                 ("l_discount", "NUMERIC"), ("l_tax", "NUMERIC"), ("l_returnflag", "VARCHAR"),
                 ("l_linestatus", "VARCHAR"), ("l_shipdate", "DATE"), ("l_commitdate", "DATE"),
                 ("l_receiptdate", "DATE"), ("l_shipinstruct", "VARCHAR"), ("l_shipmode", "VARCHAR"),
                 ("l_comment", "VARCHAR")],
}

QUERIES = [
    ("q1", "SELECT c_name FROM customer WHERE c_nationkey = 1",
     ["c_name"], {("c_name", "customer", "c_nationkey")}, {("c_name", "customer", "c_name")}),
    ("q2", "SELECT c_name FROM customer WHERE c_mktsegment = 'BUILDING'",
     ["c_name"], {("c_name", "customer", "c_mktsegment")}, {("c_name", "customer", "c_name")}),
    ("q3", "SELECT o_orderkey, o_totalprice FROM orders WHERE o_orderdate >= DATE '1995-01-01'",
     ["o_orderkey", "o_totalprice"], {("o_orderkey", "orders", "o_orderdate"),
                                      ("o_totalprice", "orders", "o_orderdate")},
     {("o_orderkey", "orders", "o_orderkey"), ("o_totalprice", "orders", "o_totalprice")}),
    ("q4", "SELECT SUM(l_quantity) AS \"sum(l_quantity)\" FROM lineitem "
           "WHERE l_shipdate >= DATE '1995-01-01' AND l_partkey = 1",
     ["sum(l_quantity)"], {("sum(l_quantity)", "lineitem", "l_shipdate"),
                           ("sum(l_quantity)", "lineitem", "l_partkey")},
     {("sum(l_quantity)", "lineitem", "l_quantity")}),
    ("q5", "SELECT s_name FROM supplier WHERE s_acctbal > 5000",
     ["s_name"], {("s_name", "supplier", "s_acctbal")}, {("s_name", "supplier", "s_name")}),
    ("q6", "SELECT p_name FROM part WHERE p_size = 15",
     ["p_name"], {("p_name", "part", "p_size")}, {("p_name", "part", "p_name")}),
]


def psql(dsn: str, sql: str) -> str:
    proc = subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t"],
        input=sql, text=True, capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/tpch_control.sqlite")
    ap.add_argument("--dsn", default="host=/tmp port=55432 user=postgres dbname=provtpch")
    ap.add_argument("--out", default="results/provsql_tpch.json")
    ap.add_argument("--csv-dir", default="/tmp/provtpch_csv")
    args = ap.parse_args()

    csv_dir = Path(args.csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(args.db)
    for table, cols in TABLES.items():
        names = [c for c, _ in cols]
        cur = src.execute(f'SELECT {", ".join(names)} FROM {table}')
        with (csv_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(names)
            writer.writerows(cur)
    src.close()

    # Recreate the database so add_provenance() is applied once per table.
    subprocess.run(["psql", "host=/tmp port=55432 user=postgres dbname=postgres",
                    "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS provtpch;"],
                   check=True, capture_output=True, text=True)
    subprocess.run(["psql", "host=/tmp port=55432 user=postgres dbname=postgres",
                    "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE provtpch;"],
                   check=True, capture_output=True, text=True)
    schema = ["SET search_path = public, provsql;", "CREATE EXTENSION IF NOT EXISTS provsql CASCADE;"]
    for table, cols in TABLES.items():
        schema.append(f"CREATE TABLE {table} ({', '.join(f'{c} {t}' for c, t in cols)});")
        schema.append(f"\\copy {table} FROM '{csv_dir / (table + '.csv')}' WITH (FORMAT csv, HEADER true)")
        schema.append(f"SELECT provsql.add_provenance('{table}');")
    psql(args.dsn, "\n".join(schema) + "\n")

    # Map source ordinals to column names.
    colmap = {}
    for table, cols in TABLES.items():
        for i, (name, _) in enumerate(cols, start=1):
            colmap[(table.casefold(), i)] = name.casefold()

    out_rows = []
    for qid, sql, outputs, control, data in QUERIES:
        select_list = ", ".join(f'q."{c}"' for c in outputs)
        inner_exprs = []
        for c in outputs:
            if c == "sum(l_quantity)":
                inner_exprs.append('"sum(l_quantity)"')
            else:
                inner_exprs.append(c)
        wrapped = (
            f"SET search_path = public, provsql;\n"
            f"SET provsql.provenance = 'where';\n"
            f"SELECT {select_list}, where_provenance(q.prov) AS src\n"
            f"FROM (SELECT {', '.join(inner_exprs)}, provenance() AS prov FROM ({sql}) sub) q;\n"
        )
        try:
            text = psql(args.dsn, wrapped)
            err = None
        except Exception as exc:  # noqa: BLE001 - record per-query failure
            text, err = "", str(exc)
        edges = set()
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < len(outputs) + 1:
                continue
            ann = next((part for part in reversed(parts) if part.startswith("{")), "")
            groups = re.findall(r"\[([^\]]*)\]", ann)
            for oi, group in enumerate(groups[:len(outputs)]):
                for table, _, ordinal in re.findall(r"([A-Za-z_][\w]*):([0-9a-f-]+):(\d+)", group):
                    key = (table.casefold(), int(ordinal))
                    if key in colmap:
                        edges.add((outputs[oi].casefold(), table.casefold(), colmap[key]))
        out_rows.append({
            "qid": qid,
            "sql": sql,
            "error": err,
            "recovered_edges": sorted(edges),
            "control_recovered": sorted(edges & control),
            "data_recovered": sorted(edges & data),
            "control_total": len(control),
            "data_total": len(data),
        })
        print(qid, "control", len(edges & control), "data", len(edges & data), "err", err)

    try:
        version = psql(args.dsn, "SELECT extversion FROM pg_extension WHERE extname = 'provsql';").strip()
    except Exception:
        version = "unknown"
    payload = {
        "engine": "ProvSQL where-provenance",
        "version": version,
        "n_control": sum(len(q[3]) for q in QUERIES),
        "n_data": sum(len(q[4]) for q in QUERIES),
        "control_recovered": sum(len(r["control_recovered"]) for r in out_rows),
        "data_recovered": sum(len(r["data_recovered"]) for r in out_rows),
        "queries": out_rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "queries"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
