#!/usr/bin/env python3
"""Print tables, columns, and a few rows for a SQLite database."""
from __future__ import annotations
import argparse
import sqlite3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--max-rows", type=int, default=5)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    for table in tables:
        print(f"\n== {table} ==")
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        print("columns:", ", ".join(f"{r[1]} {r[2]}" for r in info))
        rows = conn.execute(f'SELECT * FROM "{table}" LIMIT {args.max_rows}').fetchall()
        print("rows:")
        for row in rows:
            print("  ", row)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
