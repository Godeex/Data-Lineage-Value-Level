"""Evaluate static / machine reference / oracle / evolving methods against human gold."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from agentdb.evolve import BASE_POLICY
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

POLICIES = {
    "oracle_b3_cell": {"families": ["CELL_VALUE"], "budget": 3},
    "oracle_b10_allcell": {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 10},
}


def norm_edges(edges, names):
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        match = re.fullmatch(r"_col_(\d+)", o)
        if match and int(match.group(1)) < len(names):
            o = str(names[int(match.group(1))]).casefold().strip()
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


def metrics(pred, gold_pos, gold_neg, gold_unknown):
    tp = len(pred & gold_pos)
    fp = len(pred & gold_neg)
    fn = len(gold_pos - pred)
    unjudged = len(pred - gold_pos - gold_neg - gold_unknown)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "unjudged": unjudged,
        "precision": precision, "recall": recall, "f1": f1,
        "coverage": recall,
        "false_negative_rate": fn / (tp + fn) if (tp + fn) else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="annotations/discovery/results/gold_edges.jsonl")
    ap.add_argument("--p1", default="results/p1_coverage.jsonl")
    ap.add_argument("--main", default="data/spider_main.jsonl")
    ap.add_argument("--p2", default="results/p2_evolution.json")
    ap.add_argument("--db-dir", default="/data/gx/spider/db")
    ap.add_argument("--out", default="results/gold_eval.json")
    args = ap.parse_args()

    gold = {}
    for line in Path(args.gold).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        gold[row["qid"]] = {
            "POSITIVE": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "POSITIVE"},
            "NEGATIVE": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "NEGATIVE"},
            "UNKNOWN": {(e["output_column"].casefold().strip(), e["source_table"].casefold().strip(), e["source_column"].casefold().strip()) for e in row["edges"] if e["decision"] == "UNKNOWN"},
        }
    p1 = {json.loads(l)["qid"]: json.loads(l) for l in Path(args.p1).read_text(encoding="utf-8").splitlines()}
    main_rows = {json.loads(l)["qid"]: json.loads(l) for l in Path(args.main).read_text(encoding="utf-8").splitlines()}
    learned = json.loads(Path(args.p2).read_text(encoding="utf-8"))["learned_policies"]

    methods = defaultdict(list)
    for qid, g in gold.items():
        if qid not in p1 or qid not in main_rows:
            continue
        row = main_rows[qid]
        db_path = Path(args.db_dir) / f"{row['db_id']}.sqlite"
        names = output_names(db_path, row["sql"])
        static = norm_edges(p1[qid]["static_edges"], names)
        ref = norm_edges(p1[qid]["ref_edges"], names)
        tables = load_sqlite_tables(db_path, max_rows=30)
        script = {"sql": row["sql"], "tables": tables}

        preds = {
            "static": (static, 0),
            "machine_reference": (ref, p1[qid]["ref_executions"]),
            "reference_union_static": (ref | static, p1[qid]["ref_executions"]),
        }
        for name, policy in POLICIES.items():
            obs = limited_edges(script, policy["families"], policy["budget"])
            preds[name] = (norm_edges(obs["edges"], names), obs["executions"])
        b3 = preds["oracle_b3_cell"][0]
        preds["fixed_hybrid"] = (static | b3, preds["oracle_b3_cell"][1])
        policy = learned.get(row["category"], BASE_POLICY)
        evo = limited_edges(script, policy["families"], policy["budget"])
        preds["evolving"] = (static | norm_edges(evo["edges"], names), evo["executions"])
        lit = literal_edges(script, budget=3)
        lit_edges = norm_edges(lit["edges"], names)
        preds["oracle_literal"] = (lit_edges, lit["executions"])
        preds["literal_union_static"] = (static | lit_edges, lit["executions"])
        preds["literal_union_b10all"] = (
            preds["oracle_b10_allcell"][0] | lit_edges,
            preds["oracle_b10_allcell"][1] + lit["executions"],
        )
        preds["literal_union_evolving"] = (
            preds["evolving"][0] | lit_edges,
            preds["evolving"][1] + lit["executions"],
        )
        preds["literal_union_fixed"] = (
            preds["fixed_hybrid"][0] | lit_edges,
            preds["fixed_hybrid"][1] + lit["executions"],
        )
        preds["literal_union_reference"] = (
            ref | lit_edges,
            p1[qid]["ref_executions"] + lit["executions"],
        )
        preds["literal_union_all"] = (
            ref | static | lit_edges,
            p1[qid]["ref_executions"] + lit["executions"],
        )

        for name, (pred, cost) in preds.items():
            m = metrics(pred, g["POSITIVE"], g["NEGATIVE"], g["UNKNOWN"])
            m.update({"qid": qid, "category": row["category"], "method": name, "executions": cost})
            methods[name].append(m)

    summary = {}
    for name, rows in methods.items():
        n = len(rows)
        summary[name] = {
            "n": n,
            "macro_precision": sum(r["precision"] for r in rows) / n,
            "macro_recall": sum(r["recall"] for r in rows) / n,
            "macro_f1": sum(r["f1"] for r in rows) / n,
            "micro_tp": sum(r["tp"] for r in rows),
            "micro_fp": sum(r["fp"] for r in rows),
            "micro_fn": sum(r["fn"] for r in rows),
            "micro_unjudged": sum(r["unjudged"] for r in rows),
            "mean_executions": sum(r["executions"] for r in rows) / n,
            "per_category": {},
        }
        for cat in sorted({r["category"] for r in rows}):
            cat_rows = [r for r in rows if r["category"] == cat]
            summary[name]["per_category"][cat] = {
                "n": len(cat_rows),
                "macro_f1": sum(r["f1"] for r in cat_rows) / len(cat_rows),
                "macro_recall": sum(r["recall"] for r in cat_rows) / len(cat_rows),
                "micro_tp": sum(r["tp"] for r in cat_rows),
                "micro_fn": sum(r["fn"] for r in cat_rows),
            }
    Path(args.out).write_text(json.dumps({"summary": summary, "per_query": dict(methods)}, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(args.out).with_suffix(".jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for rows in methods.values() for r in rows) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_category"} for k, v in summary.items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
