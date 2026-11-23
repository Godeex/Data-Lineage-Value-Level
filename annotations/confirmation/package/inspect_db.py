#!/usr/bin/env python3
"""Read-only SQLite inspector for the confirmation annotation package."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--schema", action="store_true")
    ap.add_argument("--sql", default="")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"missing database: {db}")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        if args.schema or not args.sql:
            for (table,) in conn.execute("select name from sqlite_master where type='table' order by name"):
                cols = [r[1] for r in conn.execute(f'pragma table_info("{table}")')]
                print(f"{table}({', '.join(cols)})")
        if args.sql:
            cur = conn.execute(args.sql)
            print("\t".join(d[0] for d in (cur.description or [])))
            for i, row in enumerate(cur):
                if i >= args.limit:
                    break
                print("\t".join("NULL" if v is None else str(v) for v in row))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
