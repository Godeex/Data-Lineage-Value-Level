"""Build a blind human-annotation package for the literal-probing confirmation study.

Selects one query per unique SQL template from the 78-query non-gold strict pool
(42 templates), enumerates neutral candidate edges from SQL-referenced columns,
writes three blank annotator sheets, and seals the frozen fixed/literal predictions.
"""
from __future__ import annotations

import csv
import hashlib
import os
import json
import random
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "annotations/confirmation/package"
DB_SRC = Path(os.environ.get("AGENTDB_DB_DIR", "/data/gx/spider/db"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_edges(edges, names):
    import re
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        m = re.fullmatch(r"_col_(\d+)", o)
        if m and int(m.group(1)) < len(names):
            o = str(names[int(m.group(1))]).casefold().strip()
        out.add((o, str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def output_names(db_path: Path, sql: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(sql)
        return [d[0] for d in (cur.description or [])]
    except Exception:
        return []
    finally:
        conn.close()


def schema(db_path: Path) -> dict[str, list[str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        out = {}
        for (table,) in conn.execute("select name from sqlite_master where type='table'"):
            out[table] = [r[1] for r in conn.execute(f'pragma table_info("{table}")')]
        return out
    finally:
        conn.close()


def select_queries() -> list[dict]:
    main = {json.loads(l)["qid"]: json.loads(l) for l in (ROOT / "data/spider_main.jsonl").read_text().splitlines()}
    p1 = {json.loads(l)["qid"]: json.loads(l) for l in (ROOT / "results/p1_coverage.jsonl").read_text().splitlines()}
    gold = {json.loads(l)["qid"] for l in (ROOT / "annotations/discovery/results/gold_edges.jsonl").read_text().splitlines()}
    gold_sql = {main[q]["sql"].strip().casefold() for q in gold}
    pool = [
        r for q, r in main.items()
        if q not in gold and q in p1 and r["sql"].strip().casefold() not in gold_sql
    ]
    uniq: dict[str, dict] = {}
    for r in pool:
        uniq.setdefault(r["sql"].strip().casefold(), r)
    rows = sorted(uniq.values(), key=lambda r: (r["category"], r["qid"]))
    return rows


def candidate_edges(row: dict) -> tuple[list[str], list[dict], dict[str, list[str]]]:
    db_path = DB_SRC / f"{row['db_id']}.sqlite"
    sch = schema(db_path)
    outs = output_names(db_path, row["sql"])
    try:
        tree = sqlglot.parse_one(row["sql"], read="sqlite")
    except Exception:
        tree = None
    cols: set[str] = set()
    tables: set[str] = set()
    if tree is not None:
        for c in tree.find_all(exp.Column):
            cols.add(c.name.casefold())
        for t in tree.find_all(exp.Table):
            if t.name:
                tables.add(t.name)
        if any(True for _ in tree.find_all(exp.Star)):
            for t in tables:
                for c in sch.get(t, []):
                    cols.add(c.casefold())
    src: set[tuple[str, str]] = set()
    for col in cols:
        for table, columns in sch.items():
            if col in {c.casefold() for c in columns}:
                src.add((table, col))
    edges = [
        {"qid": row["qid"], "output_column": o, "source_table": t, "source_column": c}
        for o in outs for t, c in sorted(src)
    ]
    return outs, edges, sch


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "dbs").mkdir(parents=True)
    (OUT / "sealed").mkdir()
    (OUT / "schemas").mkdir()

    rows = select_queries()
    # Keep only queries with at least one neutral candidate edge.
    kept, all_edges, used_dbs = [], [], set()
    for row in rows:
        outs, edges, sch = candidate_edges(row)
        if not edges:
            continue
        kept.append({"qid": row["qid"], "db_id": row["db_id"], "category": row["category"],
                     "sql": row["sql"], "question": row.get("question", ""),
                     "output_columns": outs, "tables": sorted(sch)})
        all_edges.extend(edges)
        used_dbs.add(row["db_id"])
        (OUT / "schemas" / f"{row['db_id']}.json").write_text(json.dumps(sch, indent=1, ensure_ascii=False))

    (OUT / "queries.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + "\n")

    for db_id in sorted(used_dbs):
        shutil.copy2(DB_SRC / f"{db_id}.sqlite", OUT / "dbs" / f"{db_id}.sqlite")

    with (OUT / "candidate_edges.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["qid", "output_column", "source_table", "source_column"])
        w.writeheader(); w.writerows(all_edges)

    for annotator in ("A", "B", "C"):
        with (OUT / f"annotation_sheet_{annotator}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["qid", "annotator", "output_column", "source_table", "source_column",
                        "decision", "confidence", "evidence_type", "note"])
            for e in all_edges:
                w.writerow([e["qid"], annotator, e["output_column"], e["source_table"],
                            e["source_column"], "", "", "", ""])

    # Sealed frozen predictions: fixed hybrid and literal probing.
    preds = []
    for row in kept:
        db_path = DB_SRC / f"{row['db_id']}.sqlite"
        names = output_names(db_path, row["sql"])
        tables = load_sqlite_tables(db_path, max_rows=30)
        script = {"sql": row["sql"], "tables": tables}
        p1 = {json.loads(l)["qid"]: json.loads(l) for l in (ROOT / "results/p1_coverage.jsonl").read_text().splitlines()}
        static = norm_edges(p1[row["qid"]]["static_edges"], names)
        b3 = limited_edges(script, ["CELL_VALUE"], 3)
        lit = literal_edges(script, budget=3)
        fixed = static | norm_edges(b3["edges"], names)
        literal = norm_edges(lit["edges"], names)
        preds.append({
            "qid": row["qid"],
            "fixed_edges": sorted(fixed),
            "literal_edges": sorted(literal),
            "union_edges": sorted(fixed | literal),
            "fixed_executions": b3["executions"],
            "literal_executions": lit["executions"],
        })
    sealed = OUT / "sealed/predictions.jsonl"
    sealed.write_text("\n".join(json.dumps(p) for p in preds) + "\n")
    (OUT / "sealed/predictions.sha256").write_text(sha(sealed) + "  predictions.jsonl\n")

    hashes = {}
    for p in [ROOT / "src/agentdb/sqlite_oracle.py", ROOT / "src/agentdb/spider.py",
              ROOT / "src/agentdb/lineage.py", ROOT / "scripts/evaluate_gold.py",
              ROOT / "paper/figures/make_all_figures.py"]:
        hashes[str(p.relative_to(ROOT))] = sha(p)
    (OUT / "freeze_config.json").write_text(json.dumps({
        "frozen_on": "2026-11-18",
        "selection": "one query per unique SQL template from the 78-query non-gold strict pool; 42 templates",
        "literal_probe": {"budget_rows_per_column": 3, "families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"],
                          "candidate_order": ["type-compatible SQL literals", "boundary values", "current values"],
                          "dedup": True, "budget_exhaustion": "UNKNOWN"},
        "source_hashes": hashes,
        "sealed_predictions_sha256": sha(sealed),
    }, indent=1))

    print(json.dumps({"queries": len(kept), "candidate_edges": len(all_edges),
                      "dbs": len(used_dbs), "categories": dict(Counter(r["category"] for r in kept))}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
