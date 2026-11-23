"""Literal probe ablation on the 30 human-gold queries."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

STRUCT = re.compile(r"\b(WHERE|CASE|GROUP\s+BY|ORDER\s+BY|HAVING)\b", re.I)


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def prf(pred, pos, neg):
    tp = len(pred & pos)
    fp = len(pred & neg)
    fn = len(pos - pred)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def main() -> int:
    gold = {}
    for line in Path("annotations/discovery/results/gold_edges.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        gold[row["qid"]] = {
            "POSITIVE": {(e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()) for e in row["edges"] if e["decision"] == "POSITIVE"},
            "NEGATIVE": {(e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()) for e in row["edges"] if e["decision"] == "NEGATIVE"},
        }
    main_rows = {json.loads(l)["qid"]: json.loads(l) for l in Path("data/spider_main.jsonl").read_text(encoding="utf-8").splitlines()}
    per = defaultdict(list)
    for qid, g in gold.items():
        row = main_rows[qid]
        tables = load_sqlite_tables(Path(os.environ.get("AGENTDB_DB_DIR", "/data/gx/spider/db")) / f"{row['db_id']}.sqlite", max_rows=30)
        script = {"sql": row["sql"], "tables": tables}
        structural = bool(STRUCT.search(row["sql"]))
        variants = {
            "full": literal_edges(script, mode="full"),
            "literals_only": literal_edges(script, mode="literals"),
            "boundary_only": literal_edges(script, mode="boundary"),
            "random": literal_edges(script, mode="random"),
        }
        variants["structural_full"] = (
            literal_edges(script, mode="full") if structural
            else limited_edges(script, ["CELL_VALUE"], 3)
        )
        variants["structural_literals"] = (
            literal_edges(script, mode="literals") if structural
            else limited_edges(script, ["CELL_VALUE"], 3)
        )
        for name, out in variants.items():
            pred = norm(out["edges"])
            m = prf(pred, g["POSITIVE"], g["NEGATIVE"])
            m.update({"qid": qid, "category": row["category"], "structural": structural,
                      "executions": out["executions"], "n_edges": len(pred)})
            per[name].append(m)
    summary = {}
    for name, recs in per.items():
        n = len(recs)
        tp = sum(r["tp"] for r in recs); fp = sum(r["fp"] for r in recs); fn = sum(r["fn"] for r in recs)
        p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        summary[name] = {"n": n, "micro_tp": tp, "micro_fp": fp, "micro_fn": fn,
                         "micro_precision": p, "micro_recall": r, "micro_f1": f,
                         "macro_f1": sum(x["f1"] for x in recs) / n,
                         "mean_executions": sum(x["executions"] for x in recs) / n}
    Path("results/literal_ablation.json").write_text(json.dumps({"summary": summary, "per_query": dict(per)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
