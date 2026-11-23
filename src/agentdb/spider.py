"""Spider dataset adapter: real SQLite databases + gold SQL queries.

Used only for the P0 pilot on real schemas/rows. Spider has no column-lineage
gold labels, so this pilot measures static-vs-oracle agreement and oracle
coverage, not end-to-end accuracy.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_TYPE_MAP = {
    "INTEGER": "INT", "INT": "INT", "BIGINT": "BIGINT",
    "REAL": "DOUBLE", "FLOAT": "DOUBLE", "DOUBLE": "DOUBLE", "NUMERIC": "DOUBLE",
    "TEXT": "TEXT", "VARCHAR": "TEXT", "CHAR": "TEXT", "BLOB": "TEXT",
    "DATE": "TEXT", "DATETIME": "TEXT", "BOOLEAN": "BOOL",
}


def _map_type(sqlite_type: str) -> str:
    base = (sqlite_type or "").upper().split("(")[0].strip()
    return _TYPE_MAP.get(base, "TEXT")


def load_sqlite_tables(db_path: str | Path, max_rows: int = 200) -> dict[str, dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    try:
        table_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        tables: dict[str, dict[str, Any]] = {}
        for table in table_names:
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            columns = {row[1]: _map_type(row[2]) for row in info}
            rows = conn.execute(f'SELECT * FROM "{table}" LIMIT {max_rows}').fetchall()
            tables[table] = {"columns": columns, "rows": [list(r) for r in rows]}
        return tables
    finally:
        conn.close()


def load_queries(parquet_path: str | Path, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    import duckdb

    con = duckdb.connect()
    rows = con.execute(
        f"SELECT db_id, query, question FROM read_parquet('{parquet_path}') "
        f"LIMIT {limit} OFFSET {offset}"
    ).fetchall()
    con.close()
    return [{"db_id": r[0], "sql": r[1], "question": r[2]} for r in rows]
