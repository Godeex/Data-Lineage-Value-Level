"""P1: reference vs budgeted-oracle coverage on Spider main/stress sets."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from agentdb.data import schema_for
from agentdb.lineage import extract_static_lineage
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, reference_edges

POLICIES = {
    "b3_cell": {"families": ["CELL_VALUE"], "budget": 3},
    "b10_cell": {"families": ["CELL_VALUE"], "budget": 10},
    "b3_allcell": {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 3},
    "b10_allcell": {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 10},
}


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def prf(pred, gold):
    pred, gold = set(pred), set(gold)
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", default="data/spider_main.jsonl")
    parser.add_argument("--stress", default="data/spider_stress.jsonl")
    parser.add_argument("--db-dir", default="/data/gx/spider/db")
    parser.add_argument("--max-rows", type=int, default=30)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out", default="results/p1_coverage.jsonl")
    args = parser.parse_args()

    rows = []
    for path in (args.main, args.stress):
        p = Path(path)
        if p.exists():
            rows.extend(json.loads(line) for line in p.read_text(encoding="utf-8").splitlines())
    if args.limit:
        rows = rows[: args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []
    for idx, row in enumerate(rows):
        db_path = Path(args.db_dir) / f"{row['db_id']}.sqlite"
        try:
            tables = load_sqlite_tables(db_path, max_rows=args.max_rows)
            script = {"sql": row["sql"], "tables": tables}
            ref = reference_edges(script, timeout_s=args.timeout)
            ref_edges = norm(ref["edges"])
            static = norm(extract_static_lineage(row["sql"], schema_for(script), dialect="sqlite"))
            per_policy = {}
            for name, policy in POLICIES.items():
                obs = limited_edges(script, policy["families"], policy["budget"], timeout_s=args.timeout)
                obs_edges = norm(obs["edges"])
                precision, recall, f1 = prf(obs_edges, ref_edges)
                per_policy[name] = {
                    "n_obs": len(obs_edges),
                    "coverage": (len(obs_edges & ref_edges) / len(ref_edges)) if ref_edges else None,
                    "false_negative_rate": (len(ref_edges - obs_edges) / len(ref_edges)) if ref_edges else None,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "executions": obs["executions"],
                }
            s_precision, s_recall, s_f1 = prf(static, ref_edges)
            record = {
                "qid": row["qid"], "db_id": row["db_id"], "category": row.get("category"),
                "stress_type": row.get("stress_type"), "source": row.get("source", "natural"),
                "n_ref": len(ref_edges), "ref_executions": ref["executions"],
                "n_static": len(static), "static_precision": s_precision,
                "static_recall": s_recall, "static_f1": s_f1,
                "policies": per_policy,
                "ref_edges": sorted(ref_edges),
                "static_edges": sorted(static),
            }
            results.append(record)
        except Exception as exc:  # noqa: BLE001 - record per-query failure
            failures.append({"qid": row["qid"], "error": f"{type(exc).__name__}: {exc}"})
    with out_path.open("w", encoding="utf-8") as handle:
        for rec in results:
            handle.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    summary = {"n_rows": len(results), "n_failed": len(failures), "failures": failures[:20]}
    for group_key in ("category", "stress_type"):
        groups = defaultdict(list)
        for rec in results:
            groups[str(rec.get(group_key))].append(rec)
        summary[group_key] = {}
        for name, recs in groups.items():
            summary[group_key][name] = {
                "n": len(recs),
                "mean_ref_edges": sum(r["n_ref"] for r in recs) / len(recs),
                "mean_static_f1": sum(r["static_f1"] for r in recs) / len(recs),
                **{
                    policy: {
                        "mean_coverage": sum(
                            r["policies"][policy]["coverage"] for r in recs
                            if r["policies"][policy]["coverage"] is not None
                        ) / max(1, sum(1 for r in recs if r["policies"][policy]["coverage"] is not None)),
                        "mean_fn": sum(
                            r["policies"][policy]["false_negative_rate"] for r in recs
                            if r["policies"][policy]["false_negative_rate"] is not None
                        ) / max(1, sum(1 for r in recs if r["policies"][policy]["false_negative_rate"] is not None)),
                        "mean_exec": sum(r["policies"][policy]["executions"] for r in recs) / len(recs),
                    }
                    for policy in POLICIES
                },
            }
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_rows", "n_failed")}, ensure_ascii=False, indent=1))
    print(json.dumps(summary.get("category", {}), ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
