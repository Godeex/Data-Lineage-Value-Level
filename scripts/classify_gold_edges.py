"""Heuristic DATA / CONTROL / MIXED classification of human-gold edges."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp


def control_columns(sql: str) -> set[str]:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return set()
    cols = set()
    nodes = [exp.Where, exp.Having, exp.Group, exp.Join, exp.Case]
    # ORDER BY only changes the returned multiset when LIMIT/OFFSET is present.
    if tree.find(exp.Limit) or tree.find(exp.Offset):
        nodes.append(exp.Order)
    for node in tree.find_all(*nodes):
        for col in node.find_all(exp.Column):
            cols.add(col.name.casefold())
    return cols


def select_columns(sql: str) -> set[str]:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return set()
    cols = set()
    for node in tree.find_all(exp.Select):
        for proj in node.expressions:
            for col in proj.find_all(exp.Column):
                cols.add(col.name.casefold())
    return cols


def main() -> int:
    gold = [json.loads(l) for l in Path("annotations/discovery/results/gold_edges.jsonl").read_text(encoding="utf-8").splitlines()]
    main_rows = {json.loads(l)["qid"]: json.loads(l) for l in Path("data/spider_main.jsonl").read_text(encoding="utf-8").splitlines()}
    out = []
    counts = Counter()
    by_cat = defaultdict(Counter)
    for row in gold:
        qid = row["qid"]
        sql = main_rows[qid]["sql"]
        ctrl = control_columns(sql); sel = select_columns(sql)
        for e in row["edges"]:
            if e["decision"] != "POSITIVE":
                continue
            col = e["source_column"].casefold()
            if col in ctrl and col in sel:
                typ = "MIXED"
            elif col in ctrl:
                typ = "CONTROL"
            elif col in sel:
                typ = "DATA"
            else:
                typ = "INDIRECT"
            counts[typ] += 1
            by_cat[main_rows[qid]["category"]][typ] += 1
            out.append({"qid": qid, "output_column": e["output_column"], "source_table": e["source_table"],
                        "source_column": e["source_column"], "type": typ,
                        "category": main_rows[qid]["category"], "note": e.get("note", "")})
    Path("results/gold_edge_types.json").write_text(json.dumps({"counts": dict(counts), "by_category": by_cat, "edges": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"counts": dict(counts), "by_category": {k: dict(v) for k, v in by_cat.items()}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
