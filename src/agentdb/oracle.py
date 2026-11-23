"""Differential execution oracle: perturb source columns, observe output changes."""

from __future__ import annotations

import datetime as dt
from typing import Any

import duckdb

# A fixed perturbation is used so the oracle is deterministic and auditable.
_NUMERIC_BUMP = 100
_TEXT_SUFFIX = "_p"


def _perturb_value(value: Any, sql_type: str) -> Any:
    t = sql_type.upper()
    if value is None:
        if "INT" in t or "DOUBLE" in t or "FLOAT" in t or "DECIMAL" in t:
            return _NUMERIC_BUMP
        if "BOOL" in t:
            return True
        return "x"
    if "INT" in t or "DOUBLE" in t or "FLOAT" in t or "DECIMAL" in t:
        return value + _NUMERIC_BUMP
    if "BOOL" in t:
        return not bool(value)
    if "DATE" in t or "TIMESTAMP" in t:
        return value + dt.timedelta(days=1)
    return f"{value}{_TEXT_SUFFIX}"


def _create_tables(conn: duckdb.DuckDBPyConnection, tables: dict[str, dict[str, Any]],
                   override: tuple[str, str, int, Any] | None = None) -> None:
    for table_name, spec in tables.items():
        cols = spec["columns"]
        rows = spec["rows"]
        col_defs = ", ".join(f'"{c}" {t}' for c, t in cols.items())
        conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
        col_names = list(cols.keys())
        for row_idx, row in enumerate(rows):
            values = list(row)
            if override is not None:
                o_table, o_col, o_row, o_value = override
                if o_table == table_name and o_row == row_idx:
                    values[col_names.index(o_col)] = o_value
            placeholders = ", ".join("?" for _ in values)
            conn.execute(
                f'INSERT INTO "{table_name}" VALUES ({placeholders})', values
            )


def _run(conn: duckdb.DuckDBPyConnection, sql: str) -> tuple[list[str], list[tuple]]:
    cur = conn.execute(sql)
    description = cur.description or []
    columns = [d[0] for d in description]
    rows = cur.fetchall()
    return columns, rows


def _values_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= 1e-9
    return a == b


def _outputs_differ(
    base: tuple[list[str], list[tuple]], perturbed: tuple[list[str], list[tuple]]
) -> set[str]:
    """Order-insensitive output comparison: row order alone is not value lineage."""
    from collections import Counter

    base_cols, base_rows = base
    new_cols, new_rows = perturbed
    if [c.casefold() for c in base_cols] != [c.casefold() for c in new_cols]:
        return set(base_cols)
    if len(base_rows) != len(new_rows):
        return set(base_cols)
    changed: set[str] = set()
    for idx, col in enumerate(base_cols):
        base_vals = Counter(row[idx] for row in base_rows)
        new_vals = Counter(row[idx] for row in new_rows)
        if base_vals != new_vals:
            changed.add(col)
    return changed


def oracle_edges(script: dict[str, Any], max_witness_rows: int | None = None) -> tuple[set[tuple[str, str, str]], dict[str, Any]]:
    """Return (observed_edges, metadata) for one script.

    observed_edges are (output_col, source_table, source_col): the edge is
    *observable* if perturbing the source column changes that output.
    """
    tables = script["tables"]
    sql = script["sql"]
    base_conn = duckdb.connect()
    _create_tables(base_conn, tables)
    base = _run(base_conn, sql)
    base_conn.close()

    observed: set[tuple[str, str, str]] = set()
    tested = 0
    for table_name, spec in tables.items():
        for col, sql_type in spec["columns"].items():
            tested += 1
            witness_rows = spec["rows"][:max_witness_rows] if max_witness_rows else spec["rows"]
            for row_idx, row in enumerate(witness_rows):
                raw = row[list(spec["columns"].keys()).index(col)]
                new_value = _perturb_value(raw, sql_type)
                conn = duckdb.connect()
                _create_tables(conn, tables, override=(table_name, col, row_idx, new_value))
                perturbed = _run(conn, sql)
                conn.close()
                changed = _outputs_differ(base, perturbed)
                for out_col in changed:
                    observed.add((out_col, table_name, col))
                if changed:
                    break  # one witnessing perturbation is enough for this column
    meta = {"perturbations_tested": tested, "numeric_bump": _NUMERIC_BUMP,
            "text_suffix": _TEXT_SUFFIX}
    return observed, meta
