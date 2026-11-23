"""SQLite-backed perturbation oracle with exhaustive reference and budgeted observation.

Definitions follow THEORY.md:
  - reference (L_sem): exhaustive cell-level perturbations over all rows
  - limited (L_obs): budgeted rows / selected families
Row-level perturbations are tracked separately and are not attributed to columns.
"""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from typing import Any, Iterable

CELL_FAMILIES = ("CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE")
ROW_FAMILIES = ("ROW_DELETE", "ROW_DUPLICATE")


class QueryTimeout(RuntimeError):
    pass


def _sqlite_type(sql_type: str) -> str:
    t = (sql_type or "").upper()
    if "INT" in t or "BOOL" in t:
        return "INTEGER"
    if "DOUBLE" in t or "FLOAT" in t or "REAL" in t or "NUMERIC" in t or "DECIMAL" in t:
        return "REAL"
    return "TEXT"


def open_memory_db(tables: dict[str, dict[str, Any]], max_rows: int | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    for table, spec in tables.items():
        cols = spec["columns"]
        defs = ", ".join(f'"{c}" {_sqlite_type(t)}' for c, t in cols.items())
        conn.execute(f'CREATE TABLE "{table}" ({defs})')
        rows = spec["rows"][:max_rows] if max_rows else spec["rows"]
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    conn.commit()
    return conn


def _run(conn: sqlite3.Connection, sql: str, timeout_s: float = 3.0) -> tuple[list[str], list[Counter]]:
    deadline = time.monotonic() + timeout_s
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 5000)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in (cur.description or [])]
        rows = cur.fetchall()
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryTimeout(f"query exceeded {timeout_s}s") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
    per_col = []
    for idx in range(len(columns)):
        per_col.append(Counter(row[idx] for row in rows))
    return columns, per_col


def _changed_outputs(
    base: tuple[list[str], list[Counter]],
    perturbed: tuple[list[str], list[Counter]],
) -> set[str]:
    base_cols, base_vals = base
    new_cols, new_vals = perturbed
    if [c.casefold() for c in base_cols] != [c.casefold() for c in new_cols]:
        return {c.casefold() for c in base_cols}
    changed = set()
    for col, b, n in zip(base_cols, base_vals, new_vals):
        if b != n:
            changed.add(col.casefold())
    return changed


def _rowids(conn: sqlite3.Connection, table: str) -> list[int]:
    return [r[0] for r in conn.execute(f'SELECT rowid FROM "{table}" ORDER BY rowid')]


def _column_values(conn: sqlite3.Connection, table: str, col: str) -> list[Any]:
    return [r[0] for r in conn.execute(f'SELECT "{col}" FROM "{table}"')]


def _default_value(sql_type: str) -> Any:
    t = _sqlite_type(sql_type)
    return 1 if t in {"INTEGER", "REAL"} else "x"


def _new_value(value: Any, sql_type: str) -> Any:
    t = _sqlite_type(sql_type)
    if value is None:
        return _default_value(sql_type)
    if t in {"INTEGER", "REAL"}:
        return value + 100
    return f"{value}_p"


def _savepoint(conn: sqlite3.Connection):
    conn.execute("SAVEPOINT pert")


def _rollback(conn: sqlite3.Connection):
    conn.execute("ROLLBACK TO pert")
    conn.execute("RELEASE pert")


def _apply_cell(conn: sqlite3.Connection, table: str, col: str, rowid: int, family: str,
                sql_type: str, old_value: Any) -> bool:
    """Apply one column-level perturbation; return False if not applicable."""
    if family == "CELL_VALUE":
        new_value = _new_value(old_value, sql_type)
    elif family == "VALUE_TO_NULL":
        if old_value is None:
            return False
        new_value = None
    elif family == "NULL_TO_VALUE":
        if old_value is not None:
            return False
        new_value = _default_value(sql_type)
    else:
        raise ValueError(f"not a cell family: {family}")
    conn.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (new_value, rowid))
    return True


def _apply_row(conn: sqlite3.Connection, table: str, rowid: int, family: str) -> None:
    if family == "ROW_DELETE":
        conn.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (rowid,))
    elif family == "ROW_DUPLICATE":
        conn.execute(f'INSERT INTO "{table}" SELECT * FROM "{table}" WHERE rowid = ?', (rowid,))
    else:
        raise ValueError(f"not a row family: {family}")


def _edge_set(conn: sqlite3.Connection, sql: str, family: str, budget: int | None,
              timeout_s: float, column_level: bool) -> tuple[set[tuple[str, str, str]], int, set[str]]:
    """Run one family over a DB. budget=None means exhaustive."""
    edges: set[tuple[str, str, str]] = set()
    executions = 0
    row_affected_outputs: set[str] = set()
    base = _run(conn, sql, timeout_s)
    table_names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    for table in table_names:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        cols = [(row[1], row[2]) for row in info]
        rowids = _rowids(conn, table)
        test_rowids = rowids if budget is None else rowids[:budget]
        if column_level:
            for col, sql_type in cols:
                for rowid in test_rowids:
                    old_value = conn.execute(
                        f'SELECT "{col}" FROM "{table}" WHERE rowid = ?', (rowid,)
                    ).fetchone()[0]
                    _savepoint(conn)
                    try:
                        if not _apply_cell(conn, table, col, rowid, family, sql_type, old_value):
                            continue
                        perturbed = _run(conn, sql, timeout_s)
                        executions += 1
                        for out in _changed_outputs(base, perturbed):
                            edges.add((out, table.casefold(), col.casefold()))
                    finally:
                        _rollback(conn)
        else:
            for rowid in test_rowids:
                _savepoint(conn)
                try:
                    _apply_row(conn, table, rowid, family)
                    perturbed = _run(conn, sql, timeout_s)
                    executions += 1
                    row_affected_outputs |= _changed_outputs(base, perturbed)
                finally:
                    _rollback(conn)
    return edges, executions, row_affected_outputs



def sql_literals(sql: str) -> list:
    """Extract literal values from a SQL string (numbers and strings)."""
    try:
        import sqlglot
        from sqlglot import exp
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return []
    values = []
    for node in tree.find_all(exp.Literal):
        raw = node.this
        values.append(str(raw))
        if not node.is_string:
            try:
                values.append(int(raw))
            except (TypeError, ValueError):
                pass
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                pass
    return values


def _candidate_values(sql_type: str, literals: list, mode: str = "full", rng=None, n_random: int = 12) -> list:
    """Build targeted perturbation candidates from SQL literals + extremes.

    mode:
      full      - SQL literals + boundaries (default)
      literals  - only SQL literals
      boundary  - only boundary/extreme values
      random    - random type-matched values (same count as full)
    """
    t = _sqlite_type(sql_type)
    cands = []
    if mode in {"full", "literals"}:
        for lit in literals:
            cands.append(lit)
            if isinstance(lit, (int, float)):
                cands.append(str(lit))
            elif t in {"INTEGER", "REAL"}:
                try:
                    cands.append(float(lit))
                except (TypeError, ValueError):
                    pass
    if mode in {"full", "boundary"}:
        if t in {"INTEGER", "REAL"}:
            cands.extend([-1000000, 1000000, 0, 1])
        else:
            cands.extend(["", "x", "0", "1", "2", "5", "9"])
    if mode == "random":
        rng = rng or __import__("random").Random(42)
        for _ in range(n_random):
            if t in {"INTEGER", "REAL"}:
                cands.append(rng.randint(-1000, 1000))
            else:
                cands.append(f"rand_{rng.randint(0, 9999)}")
    # Deduplicate while preserving order.
    seen = set()
    out = []
    for c in cands:
        key = (type(c).__name__, repr(c))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def reference_edges(script: dict[str, Any], timeout_s: float = 3.0) -> dict[str, Any]:
    """Exhaustive cell-level reference L_sem over CELL_FAMILIES."""
    conn = open_memory_db(script["tables"])
    try:
        edges: set[tuple[str, str, str]] = set()
        executions = 0
        for family in CELL_FAMILIES:
            fam_edges, fam_exec, _ = _edge_set(conn, script["sql"], family, None, timeout_s, True)
            edges |= fam_edges
            executions += fam_exec
        return {"edges": edges, "executions": executions, "families": list(CELL_FAMILIES)}
    finally:
        conn.close()


def limited_edges(script: dict[str, Any], families: Iterable[str], budget: int,
                  timeout_s: float = 3.0) -> dict[str, Any]:
    """Budgeted L_obs: selected cell families, first `budget` rowids per column."""
    conn = open_memory_db(script["tables"])
    try:
        edges: set[tuple[str, str, str]] = set()
        executions = 0
        for family in families:
            if family not in CELL_FAMILIES:
                raise ValueError(f"limited_edges only supports cell families: {family}")
            fam_edges, fam_exec, _ = _edge_set(conn, script["sql"], family, budget, timeout_s, True)
            edges |= fam_edges
            executions += fam_exec
        return {"edges": edges, "executions": executions, "families": list(families), "budget": budget}
    finally:
        conn.close()



def literal_edges(script: dict[str, Any], budget: int | None = 3, timeout_s: float = 3.0,
                  max_candidates: int = 12, mode: str = "full", seed: int = 42) -> dict[str, Any]:
    """Predicate-aware probe: perturb cells toward SQL literals and extremes.

    ``budget=None`` enumerates every row in the loaded snapshot, which turns
    the probe into an exhaustive search over the declared candidate space.
    """
    conn = open_memory_db(script["tables"])
    try:
        base = _run(conn, script["sql"], timeout_s)
        literals = sql_literals(script["sql"])
        import random as _random
        rng = _random.Random(seed)
        edges: set[tuple[str, str, str]] = set()
        executions = 0
        table_names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for table in table_names:
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            rowids = _rowids(conn, table) if budget is None else _rowids(conn, table)[:budget]
            for col, sql_type in [(row[1], row[2]) for row in info]:
                candidates = _candidate_values(sql_type, literals, mode=mode, rng=rng)[:max_candidates]
                for rowid in rowids:
                    old_value = conn.execute(
                        f'SELECT "{col}" FROM "{table}" WHERE rowid = ?', (rowid,)
                    ).fetchone()[0]
                    for cand in candidates:
                        if cand == old_value:
                            continue
                        _savepoint(conn)
                        try:
                            conn.execute(
                                f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (cand, rowid)
                            )
                            perturbed = _run(conn, script["sql"], timeout_s)
                            executions += 1
                            for out in _changed_outputs(base, perturbed):
                                edges.add((out, table.casefold(), col.casefold()))
                        finally:
                            _rollback(conn)
        return {"edges": edges, "executions": executions, "literals": literals}
    finally:
        conn.close()


def row_influence(script: dict[str, Any], timeout_s: float = 3.0) -> dict[str, Any]:
    """Row-level influence: which output columns change when a row is deleted/duplicated."""
    conn = open_memory_db(script["tables"])
    try:
        affected: set[str] = set()
        executions = 0
        for family in ROW_FAMILIES:
            _, fam_exec, outs = _edge_set(conn, script["sql"], family, None, timeout_s, False)
            affected |= outs
            executions += fam_exec
        return {"affected_outputs": affected, "executions": executions}
    finally:
        conn.close()
