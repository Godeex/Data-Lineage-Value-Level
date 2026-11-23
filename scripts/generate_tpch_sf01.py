#!/usr/bin/env python3
"""Generate the TPC-H SF0.1 SQLite control database used by tpch_scale.py.

The generated file is intentionally not stored in the repository (about 107 MB).
Requires DuckDB with the tpch and sqlite extensions.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import duckdb

TABLES = ["customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tpch_sf01.sqlite")
    ap.add_argument("--sf", type=float, default=0.1)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    con = duckdb.connect()
    con.execute("INSTALL tpch; LOAD tpch;")
    t0 = time.time()
    con.execute(f"CALL dbgen(sf={args.sf})")
    n = con.execute("SELECT COUNT(*) FROM lineitem").fetchone()[0]
    print(f"generated SF{args.sf}: {n:,} lineitem rows in {time.time() - t0:.1f}s")
    if n < 100_000:
        raise SystemExit("expected a 10^5+ lineitem instance for the scale control")

    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{out}' AS s (TYPE sqlite);")
    for table in TABLES:
        con.execute(f"CREATE TABLE s.{table} AS SELECT * FROM {table}")
    con.execute("DETACH s")
    con.close()
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
