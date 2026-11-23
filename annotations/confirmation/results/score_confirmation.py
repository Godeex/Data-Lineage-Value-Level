#!/usr/bin/env python3
"""Score frozen fixed/literal/union predictions against adjudicated human gold."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

DECISIONS = {"POSITIVE", "NEGATIVE", "UNKNOWN", "DISPUTED"}


def edge_key(rec):
    return (str(rec["output_column"]).casefold().strip(),
            str(rec["source_table"]).casefold().strip(),
            str(rec["source_column"]).casefold().strip())


def load_gold(path):
    gold = defaultdict(lambda: {"POSITIVE": set(), "NEGATIVE": set(), "UNKNOWN": set()})
    disputed = 0
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        d = str(rec.get("decision", "UNKNOWN")).upper()
        if d == "DISPUTED":
            d = "UNKNOWN"
            disputed += 1
        if d not in DECISIONS:
            d = "UNKNOWN"
        gold[rec["qid"]][d].add(edge_key(rec))
    return gold, disputed


def load_preds(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["qid"]] = {k: {tuple(x) for x in rec[k]} for k in ("fixed_edges", "literal_edges", "union_edges")}
    return out


def metrics(pred, g):
    tp = len(pred & g["POSITIVE"])
    fp = len(pred & g["NEGATIVE"])
    fn = len(g["POSITIVE"] - pred)
    unjudged = len(pred - g["POSITIVE"] - g["NEGATIVE"] - g["UNKNOWN"])
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "unjudged": unjudged,
            "precision": p, "recall": r, "f1": f1}


def bootstrap(a, b, n=10000, seed=42):
    rng = random.Random(seed)
    diff = [x - y for x, y in zip(a, b)]
    means = []
    for _ in range(n):
        means.append(sum(diff[rng.randrange(len(diff))] for _ in range(len(diff))) / len(diff))
    means.sort()
    lo, hi = means[int(0.025 * n)], means[int(0.975 * n) - 1]
    le = sum(m <= 0 for m in means) / n
    ge = sum(m >= 0 for m in means) / n
    return {"n": len(diff), "mean_diff": sum(diff) / len(diff), "ci95": [lo, hi],
            "p_two_sided": min(1.0, 2 * min(le, ge))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="gold_final.jsonl")
    ap.add_argument("--preds", default="sealed/predictions.jsonl")
    ap.add_argument("--out", default="confirmation_results.json")
    args = ap.parse_args()

    gold, disputed = load_gold(args.gold)
    preds = load_preds(args.preds)
    qids = sorted(set(gold) & set(preds))
    print(f"matched queries: {len(qids)}; disputed->UNKNOWN: {disputed}")

    per = {m: [] for m in ("fixed", "literal", "union")}
    for qid in qids:
        for name, key in (("fixed", "fixed_edges"), ("literal", "literal_edges"), ("union", "union_edges")):
            m = metrics(preds[qid][key], gold[qid])
            m.update({"qid": qid})
            per[name].append(m)

    def summarize(rows):
        n = len(rows)
        return {
            "n": n,
            "macro_f1": sum(r["f1"] for r in rows) / n,
            "macro_precision": sum(r["precision"] for r in rows) / n,
            "macro_recall": sum(r["recall"] for r in rows) / n,
            "micro_tp": sum(r["tp"] for r in rows),
            "micro_fp": sum(r["fp"] for r in rows),
            "micro_fn": sum(r["fn"] for r in rows),
            "micro_unjudged": sum(r["unjudged"] for r in rows),
        }

    report = {name: summarize(rows) for name, rows in per.items()}
    for name in report:
        tp, fp, fn = report[name]["micro_tp"], report[name]["micro_fp"], report[name]["micro_fn"]
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        report[name]["micro_precision"] = p
        report[name]["micro_recall"] = r
        report[name]["micro_f1"] = 2 * p * r / (p + r) if p + r else 0.0

    fixed_f1 = [r["f1"] for r in per["fixed"]]
    literal_f1 = [r["f1"] for r in per["literal"]]
    union_f1 = [r["f1"] for r in per["union"]]
    report["comparisons"] = {
        "literal_minus_fixed": bootstrap(literal_f1, fixed_f1),
        "union_minus_fixed": bootstrap(union_f1, fixed_f1),
    }
    Path(args.out).write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
