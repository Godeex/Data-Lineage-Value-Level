"""Large-set evaluation with a silver reference (reference ∪ literal probe).

No new human annotation. Silver is validated on the 30 human gold:
reference ∪ literal has P=1.000 / R=0.977 on gold (RESULTS_HUMAN_GOLD.md).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from agentdb.evolve import BASE_POLICY
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

STRUCTURAL_RE = re.compile(r"\b(WHERE|CASE|GROUP\s+BY|ORDER\s+BY|HAVING)\b", re.I)


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def metrics(pred, silver):
    tp = len(pred & silver)
    outside = len(pred - silver)
    missing = len(silver - pred)
    precision = tp / (tp + outside) if (tp + outside) else 0.0
    recall = tp / (tp + missing) if (tp + missing) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "outside": outside, "missing": missing,
            "precision": precision, "recall": recall, "f1": f1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default="data/spider_main.jsonl")
    ap.add_argument("--stress", default="data/spider_stress.jsonl")
    ap.add_argument("--p1", default="results/p1_coverage.jsonl")
    ap.add_argument("--p2", default="results/p2_evolution.json")
    ap.add_argument("--db-dir", default="/data/gx/spider/db")
    ap.add_argument("--out", default="results/silver_eval.json")
    args = ap.parse_args()

    rows = []
    for path in (args.main, args.stress):
        p = Path(path)
        if p.exists():
            rows.extend(json.loads(line) for line in p.read_text(encoding="utf-8").splitlines())
    p1 = {json.loads(line)["qid"]: json.loads(line) for line in Path(args.p1).read_text(encoding="utf-8").splitlines()}
    learned = json.loads(Path(args.p2).read_text(encoding="utf-8"))["learned_policies"]

    per_method = defaultdict(list)
    for row in rows:
        qid = row["qid"]
        if qid not in p1:
            continue
        ref = norm(p1[qid]["ref_edges"])
        static = norm(p1[qid]["static_edges"])
        try:
            tables = load_sqlite_tables(Path(args.db_dir) / f"{row['db_id']}.sqlite", max_rows=30)
            script = {"sql": row["sql"], "tables": tables}
            lit_out = literal_edges(script, budget=3)
            lit = norm(lit_out["edges"])
            b3_out = limited_edges(script, ["CELL_VALUE"], 3)
            b3 = norm(b3_out["edges"])
            b10_out = limited_edges(script, ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], 10)
            b10 = norm(b10_out["edges"])
            policy = learned.get(row["category"], BASE_POLICY)
            evo_out = limited_edges(script, policy["families"], policy["budget"])
            evo = norm(evo_out["edges"])
        except Exception as exc:  # noqa: BLE001
            print("skip", qid, type(exc).__name__, exc)
            continue
        silver = ref | lit
        structural = bool(STRUCTURAL_RE.search(row["sql"]))
        preds = {
            "static": (static, 0),
            "machine_reference": (ref, p1[qid]["ref_executions"]),
            "oracle_b3_cell": (b3, b3_out["executions"]),
            "oracle_b10_allcell": (b10, b10_out["executions"]),
            "fixed_hybrid": (static | b3, b3_out["executions"]),
            "evolving": (static | evo, evo_out["executions"]),
            "literal": (lit, lit_out["executions"]),
            "literal_union_evolving": (static | evo | lit, evo_out["executions"] + lit_out["executions"]),
            "predicate_aware": (static | evo | (lit if structural else set()),
                                evo_out["executions"] + (lit_out["executions"] if structural else 0)),
        }
        for name, (pred, cost) in preds.items():
            m = metrics(pred, silver)
            m.update({"qid": qid, "category": row["category"],
                      "stress_type": row.get("stress_type"), "n_silver": len(silver),
                      "structural": structural, "executions": cost})
            per_method[name].append(m)

    summary = {}
    for name, recs in per_method.items():
        n = len(recs)
        summary[name] = {
            "n": n,
            "micro_tp": sum(r["tp"] for r in recs),
            "micro_outside": sum(r["outside"] for r in recs),
            "micro_missing": sum(r["missing"] for r in recs),
            "macro_f1": sum(r["f1"] for r in recs) / n if n else 0.0,
            "mean_executions": sum(r["executions"] for r in recs) / n if n else 0.0,
            "per_category": {},
        }
        for cat in sorted({r["category"] for r in recs}):
            c = [r for r in recs if r["category"] == cat]
            summary[name]["per_category"][cat] = {
                "n": len(c),
                "macro_f1": sum(r["f1"] for r in c) / len(c),
                "micro_tp": sum(r["tp"] for r in c),
                "micro_missing": sum(r["missing"] for r in c),
            }
    Path(args.out).write_text(json.dumps({"summary": summary, "per_query": dict(per_method)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_category"} for k, v in summary.items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
