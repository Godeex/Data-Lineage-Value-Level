#!/usr/bin/env python3
"""Single-cell perturbation probe restricted to the 492 candidate edges.

For each query, all columns of the SQL-referenced base tables are perturbed one
cell at a time (CELL_VALUE / VALUE_TO_NULL / NULL_TO_VALUE); the query is
re-executed and the multiset of every output column is compared.  A witness is
recorded only for triples that appear in ``candidate_edges.csv``.

The candidate value domain is deliberately broad (same-column values, SQL
literals, +/-1, an extreme sentinel, NULL): it is only used to decide whether an
edge is observable on this instance, not to define the gold.

Usage:
    python tools/probe_candidates.py --out tools/evidence.json
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
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
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
    """Broad candidate replacements, most informative first."""
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
        cands.append(("CELL_VALUE", -1e6))
        cands.append(("CELL_VALUE", 0))
        cands.append(("CELL_VALUE", value + 100))
        cands.append(("VALUE_TO_NULL", None))
        for other in pool["num"][:2]:
            cands.append(("CELL_VALUE", other))
    else:
        s = str(value)
        cands.append(("CELL_VALUE", s + "_p"))
        for other in colvals:
            if other is not None and other != value:
                cands.append(("CELL_VALUE", other))
            if len(cands) >= 3:
                break
        cands.append(("VALUE_TO_NULL", None))
        cands.append(("CELL_VALUE", ""))
        cands.append(("CELL_VALUE", "zzz_p"))
        for other in pool["lit_num"][:4]:
            cands.append(("CELL_VALUE", int(other) if float(other).is_integer() else str(other)))
        for other in pool["num"][:2]:
            cands.append(("CELL_VALUE", int(other) if float(other).is_integer() else str(other)))
        for other in pool["lit_text"][:2]:
            cands.append(("CELL_VALUE", other))

    seen, uniq = set(), []
    for fam, v in cands:
        if len(uniq) >= 12:
            break
        key = (fam, repr(v))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((fam, v))
    return uniq


def build_pool(con, sql, tables):
    lit_text = re.findall(r"'([^']*)'", sql)
    lit_exact, lit_near = [], []
    for num in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", sql):
        try:
            f = float(num)
        except ValueError:
            continue
        lit_exact.append(f)
        lit_near.extend([f - 1, f + 1])
    nums, texts = [], []
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

    return {"lit_num": dedup(lit_exact + lit_near, 9), "lit_text": dedup(lit_text, 6),
            "num": dedup(nums, 8), "text": dedup(texts, 8)}


def run_query(con, sql):
    cur = con.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def analyse(con, sql, tables, wanted):
    info = {"output_columns": [], "n_rows": None, "error": None, "edges": {}, "unreferenced": []}
    try:
        cols, rows = run_query(con, sql)
    except Exception as exc:
        info["error"] = str(exc)
        return info
    info["output_columns"] = cols
    info["n_rows"] = len(rows)
    base = counters(rows, len(cols))
    pool = build_pool(con, sql, tables)
    lower_sql = sql.casefold()

    for table in tables:
        pragma = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        for col, ctype in [(r[1], r[2]) for r in pragma]:
            targets = [o for (o, t, c) in wanted if t == table.casefold() and c == col.casefold()]
            if not targets:
                continue
            try:
                cells = con.execute(f'SELECT rowid, "{col}" FROM "{table}"').fetchall()
            except sqlite3.Error:
                continue
            colvals = list({v for _, v in cells if v is not None})[:6]
            witnesses = collections.defaultdict(list)
            done = set()
            for rowid, value in cells:
                if done >= {t for t in targets}:
                    break
                for fam, new in candidates(value, ctype, colvals, pool):
                    if new is None and value is None:
                        continue
                    if new is not None and value is not None and repr(new) == repr(value):
                        continue
                    con.execute("SAVEPOINT pert")
                    changed, err = [], None
                    try:
                        con.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (new, rowid))
                        pcols, prows = run_query(con, sql)
                        if pcols != cols:
                            changed = list(cols)
                        else:
                            pc = counters(prows, len(cols))
                            changed = [cols[i] for i in range(len(cols)) if pc[i] != base[i]]
                    except Exception as exc:
                        err = str(exc)
                        changed = list(cols)
                    con.execute("ROLLBACK TO pert")
                    con.execute("RELEASE pert")
                    for o in changed:
                        if o.casefold() in {x.casefold() for x in targets} and len(witnesses[o]) < 3:
                            witnesses[o].append({"family": fam, "rowid": rowid,
                                                 "old": repr(value), "new": repr(new), "error": err})
                            done.add(o.casefold())
            for o in cols:
                if witnesses.get(o):
                    info["edges"][f"{o}\u0001{table}\u0001{col}"] = {
                        "output_column": o, "source_table": table, "source_column": col,
                        "witnesses": witnesses[o]}
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(col.casefold())}(?![A-Za-z0-9_])", lower_sql) is None:
                info["unreferenced"].append([table, col])
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tools/evidence.json")
    ap.add_argument("--qid", nargs="*")
    args = ap.parse_args()

    queries = [json.loads(l) for l in (PKG / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.qid:
        queries = [q for q in queries if q["qid"] in set(args.qid)]
    want = collections.defaultdict(set)
    import csv
    with (PKG / "candidate_edges.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            want[row["qid"].strip()].add((row["output_column"].strip().casefold(),
                                          row["source_table"].strip().casefold(),
                                          row["source_column"].strip().casefold()))

    result = {}
    for q in queries:
        db = PKG / "dbs" / f"{q['db_id']}.sqlite"
        con = sqlite3.connect(db, isolation_level=None)
        tables = referenced_tables(q["sql"], table_names(db))
        info = analyse(con, q["sql"], tables, want[q["qid"]])
        con.close()
        info["referenced_tables"] = tables
        result[q["qid"]] = info
        print(f"{q['qid']:<20} rows={info['n_rows']!s:<4} edges={len(info['edges'])} "
              f"unref={len(info['unreferenced'])} {info['error'] or ''}")
    Path(args.out).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
