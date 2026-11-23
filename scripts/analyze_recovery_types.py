"""Classify the edges added by literal probing over the machine reference + static union.

Reads cached reference/static edges from results/p1_coverage.jsonl and re-runs
only the literal oracle on the 30 human-gold queries.  Output:
results/gold_recovery_types.json
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges


def norm_edges(edges, names):
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


def main() -> int:
    db_dir = Path(os.environ.get("AGENTDB_DB_DIR", "/data/gx/spider/db"))
    main_rows = {
        json.loads(line)["qid"]: json.loads(line)
        for line in Path("data/spider_main.jsonl").read_text().splitlines()
    }
    p1 = {
        json.loads(line)["qid"]: json.loads(line)
        for line in Path("results/p1_coverage.jsonl").read_text().splitlines()
    }
    gold = {}
    for line in Path("annotations/discovery/results/gold_edges.jsonl").read_text().splitlines():
        row = json.loads(line)
        gold[row["qid"]] = {
            "POSITIVE": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "POSITIVE"},
            "NEGATIVE": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "NEGATIVE"},
            "UNKNOWN": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "UNKNOWN"},
        }
    types = {
        (e["qid"], e["output_column"].casefold().strip(),
         e["source_table"].casefold().strip(), e["source_column"].casefold().strip()): e["type"]
        for e in json.loads(Path("results/gold_edge_types.json").read_text())["edges"]
    }

    added = []
    trans = {"TP_TP": 0, "FN_TP": 0, "TP_FN": 0, "FN_FN": 0,
             "TN_TN": 0, "FP_FP": 0, "TN_FP": 0, "FP_TN": 0}
    trans_types = Counter()
    for qid, g in gold.items():
        row = main_rows[qid]
        db_path = db_dir / f"{row['db_id']}.sqlite"
        names = output_names(db_path, row["sql"])
        ref = norm_edges(p1[qid]["ref_edges"], names)
        static = norm_edges(p1[qid]["static_edges"], names)
        tables = load_sqlite_tables(db_path, max_rows=30)
        lit = literal_edges({"sql": row["sql"], "tables": tables}, budget=3)
        lit_edges = norm_edges(lit["edges"], names)
        b3 = limited_edges({"sql": row["sql"], "tables": tables}, ["CELL_VALUE"], 3)
        fixed_edges = static | norm_edges(b3["edges"], names)
        for edge in g["POSITIVE"]:
            a, b = edge in fixed_edges, edge in lit_edges
            trans[("TP" if a else "FN") + "_" + ("TP" if b else "FN")] += 1
            etype = types.get((qid, edge[0], edge[1], edge[2]), "UNLABELED")
            if (not a) and b:
                trans_types[f"gained/{etype}"] += 1
            if a and (not b):
                trans_types[f"lost/{etype}"] += 1
        for edge in g["NEGATIVE"]:
            a, b = edge in fixed_edges, edge in lit_edges
            trans[("FP" if a else "TN") + "_" + ("FP" if b else "TN")] += 1
        for edge in sorted(lit_edges - (ref | static)):
            decision = next((k for k, v in g.items() if edge in v), "OUTSIDE")
            added.append({
                "qid": qid,
                "category": row["category"],
                "output_column": edge[0],
                "source_table": edge[1],
                "source_column": edge[2],
                "decision": decision,
                "type": types.get((qid, edge[0], edge[1], edge[2]), "UNLABELED"),
                "executions": lit["executions"],
            })

    counts = Counter((e["decision"], e["type"]) for e in added)
    payload = {
        "n_added": len(added),
        "counts": {f"{d}/{t}": n for (d, t), n in sorted(counts.items())},
        "transitions": trans,
        "transition_types": dict(sorted(trans_types.items())),
        "edges": added,
    }
    Path("results/gold_recovery_types.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(json.dumps(payload, indent=1, ensure_ascii=False)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
