#!/usr/bin/env python3
"""Broad instance-level perturbation oracle for the 30-query annotation package.

For every (query, referenced base table, column) pair this script applies
single-cell perturbations (CELL_VALUE / VALUE_TO_NULL / NULL_TO_VALUE) over a
broad candidate set, re-executes the query, and records which output columns
change their multiset.  The result is *evidence*, not gold: a witness proves a
POSITIVE edge, absence of a witness is only "not observed".

Usage:
    python tools/perturb_oracle.py --out evidence.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def table_names(db: Path) -> list[str]:
    con = sqlite3.connect(db)
    names = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    con.close()
    return names


def referenced_tables(sql: str, names: list[str]) -> list[str]:
    out = []
    for n in names:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", sql, re.I):
            out.append(n)
    return out


def counters(rows, ncol):
    return [collections.Counter(repr(r[i]) for r in rows) for i in range(ncol)]


def candidates(value, coltype, colvals, pool):
    """Candidate replacement values for one cell (capped, literal-first)."""
    cands: list[tuple[str, object]] = []
    isnum = isinstance(value, (int, float)) and not isinstance(value, bool)
    if value is None:
        if coltype.upper() in ("INTEGER", "REAL", "NUMERIC", ""):
            cands.append(("NULL_TO_VALUE", 0))
        cands.append(("NULL_TO_VALUE", "v0_0"))
    elif isnum:
        for delta in (1, -1):
            cands.append(("CELL_VALUE", value + delta))
        for other in pool["lit_num"]:
            cands.append(("CELL_VALUE", other))
        cands.append(("CELL_VALUE", 0))
        cands.append(("CELL_VALUE", -1e6))
        cands.append(("CELL_VALUE", value + 100))
        cands.append(("VALUE_TO_NULL", None))
        for other in pool["num"]:
            cands.append(("CELL_VALUE", other))
    else:
        s = str(value)
        cands.append(("CELL_VALUE", s + "_p"))
        cands.append(("VALUE_TO_NULL", None))
        cands.append(("CELL_VALUE", ""))
        cands.append(("CELL_VALUE", "zzz_p"))
        for other in pool["lit_text"]:
            cands.append(("CELL_VALUE", other))
        for other in pool["lit_num"]:
            cands.append(("CELL_VALUE", int(other) if float(other).is_integer() else str(other)))
        for other in pool["num"][:3]:
            cands.append(("CELL_VALUE", int(other) if float(other).is_integer() else str(other)))
        for other in pool["text"]:
            cands.append(("CELL_VALUE", other))
        for other in colvals:
            if other is not None and other != value:
                cands.append(("CELL_VALUE", other))
                break

    seen, uniq = set(), []
    for fam, v in cands:
        if len(uniq) >= 10:
            break
        key = (fam, repr(v))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((fam, v))
    return uniq


def build_pool(con, sql, tables):
    """Values worth trying as replacements: SQL literals + sampled column values."""
    lit_text = [t for t in re.findall(r"'([^']*)'", sql)]
    lit_num: list[float] = []
    for num in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", sql):
        try:
            f = float(num)
        except ValueError:
            continue
        lit_num.extend([f - 1, f, f + 1])
    nums: list[float] = []
    texts: list[str] = []
    for table in tables:
        try:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        except sqlite3.Error:
            continue
        for col in cols:
            try:
                vals = [r[0] for r in con.execute(f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT 4')]
            except sqlite3.Error:
                continue
            for v in vals:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums.append(float(v))
                elif isinstance(v, str):
                    texts.append(v)

    def dedup(items, cap):
        out, seen = [], set()
        for x in items:
            k = repr(x)
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
            if len(out) >= cap:
                break
        return out

    return {
        "lit_num": dedup(lit_num, 9),
        "lit_text": dedup(lit_text, 6),
        "num": dedup(nums, 8),
        "text": dedup(texts, 8),
    }


def run_query(con, sql):
    cur = con.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return cols, rows


def analyse(con, sql, tables):
    info = {"output_columns": [], "n_rows": None, "error": None, "edges": {}}
    con.execute("SAVEPOINT base")
    try:
        cols, rows = run_query(con, sql)
    except Exception as exc:  # pragma: no cover - data dependent
        con.execute("ROLLBACK TO base")
        con.execute("RELEASE base")
        info["error"] = str(exc)
        return info
    con.execute("RELEASE base")

    info["output_columns"] = cols
    info["n_rows"] = len(rows)
    info["empty"] = len(rows) == 0
    base = counters(rows, len(cols))
    pool = build_pool(con, sql, tables)

    for table in tables:
        pragma = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        coltypes = {r[1]: r[2] for r in pragma}
        for col, ctype in coltypes.items():
            try:
                cells = con.execute(f'SELECT rowid, "{col}" FROM "{table}"').fetchall()
            except sqlite3.Error:
                continue
            colvals = list({v for _, v in cells if v is not None})[:6]
            witnesses = collections.defaultdict(list)
            for rowid, value in cells:
                if len(witnesses) == len(cols):
                    break
                for fam, new in candidates(value, ctype, colvals, pool):
                    if new is None and value is None:
                        continue
                    if new is not None and value is not None and repr(new) == repr(value):
                        continue
                    con.execute("SAVEPOINT pert")
                    changed = []
                    err = None
                    try:
                        con.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (new, rowid))
                        pcols, prows = run_query(con, sql)
                        if pcols != cols:
                            changed = list(cols)
                        else:
                            pc = counters(prows, len(cols))
                            changed = [cols[i] for i in range(len(cols)) if pc[i] != base[i]]
                    except Exception as exc:  # perturbation broke the query
                        err = str(exc)
                        changed = list(cols)
                    con.execute("ROLLBACK TO pert")
                    con.execute("RELEASE pert")
                    for o in changed:
                        if len(witnesses[o]) < 5:
                            witnesses[o].append(
                                {
                                    "family": fam,
                                    "rowid": rowid,
                                    "old": repr(value),
                                    "new": repr(new),
                                    "error": err,
                                }
                            )
            for o in cols:
                if witnesses.get(o):
                    key = f"{o}\u0001{table}\u0001{col}"
                    info["edges"][key] = {
                        "output_column": o,
                        "source_table": table,
                        "source_column": col,
                        "witnesses": witnesses[o],
                    }
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence.json")
    ap.add_argument("--qid", nargs="*", default=None, help="only these qids (debug)")
    args = ap.parse_args()

    queries = [json.loads(l) for l in (PKG / "sample_30.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.qid:
        queries = [q for q in queries if q["qid"] in set(args.qid)]
    result = {}
    for q in queries:
        db = PKG / "dbs" / f"{q['db_id']}.sqlite"
        con = sqlite3.connect(db, isolation_level=None)
        tables = referenced_tables(q["sql"], table_names(db))
        info = analyse(con, q["sql"], tables)
        con.close()
        info["referenced_tables"] = tables
        result[q["qid"]] = info
        print(
            f"{q['qid']:<18} rows={info['n_rows']!s:<4} cols={info['output_columns']} edges={len(info['edges'])}"
        )
    (PKG / args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
