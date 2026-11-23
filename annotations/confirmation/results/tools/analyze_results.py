#!/usr/bin/env python3
"""Post-hoc analysis for the confirmation results (per category, sensitivity)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def key(o, t, c):
    return (str(o).casefold().strip(), str(t).casefold().strip(), str(c).casefold().strip())


gold = {}
cats = {}
for line in (PKG / "queries.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        q = json.loads(line)
        cats[q["qid"]] = q["category"]
for line in (PKG / "gold_final.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        gold[(r["qid"], *key(r["output_column"], r["source_table"], r["source_column"]))] = r["decision"]

preds = {}
for line in (PKG / "sealed" / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        preds[r["qid"]] = {k: {tuple(x) for x in r[k]} for k in ("fixed_edges", "literal_edges", "union_edges")}

gold_by_q = defaultdict(lambda: defaultdict(set))
for (qid, o, t, c), d in gold.items():
    gold_by_q[qid][d].add((o, t, c))

methods = (("fixed", "fixed_edges"), ("literal", "literal_edges"), ("union", "union_edges"))


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


lines = ["# 确认集结果分析", ""]
lines += ["## 1. gold 分布", "", "| category | queries | POS | NEG | UNK |", "|---|---|---|---|---|"]
for cat in sorted(set(cats.values())):
    qs = [q for q in cats if cats[q] == cat]
    c = Counter()
    for q in qs:
        for d in ("POSITIVE", "NEGATIVE", "UNKNOWN"):
            c[d] += len(gold_by_q[q][d])
    lines.append(f"| {cat} | {len(qs)} | {c['POSITIVE']} | {c['NEGATIVE']} | {c['UNKNOWN']} |")

lines += ["", "## 2. 按类别的 micro P/R/F1", "",
          "| category | method | TP | FP | FN | P | R | F1 |", "|---|---|---|---|---|---|---|---|"]
summary = {}
for cat in sorted(set(cats.values())):
    qs = [q for q in cats if cats[q] == cat]
    for name, k in methods:
        tp = fp = fn = 0
        for q in qs:
            pred = preds[q][k]
            tp += len(pred & gold_by_q[q]["POSITIVE"])
            fp += len(pred & gold_by_q[q]["NEGATIVE"])
            fn += len(gold_by_q[q]["POSITIVE"] - pred)
        p, r, f1 = prf(tp, fp, fn)
        summary[f"{cat}/{name}"] = {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": r, "f1": f1}
        lines.append(f"| {cat} | {name} | {tp} | {fp} | {fn} | {p:.3f} | {r:.3f} | {f1:.3f} |")

lines += ["", "## 3. 预测落在 UNKNOWN 边上的数量（不计入 P/R）", "",
          "| method | pred on UNKNOWN |", "|---|---|"]
for name, k in methods:
    n = sum(len({e for e in preds[q][k] if gold.get((q, *e)) == 'UNKNOWN'}) for q in preds)
    summary[f"unjudged/{name}"] = n
    lines.append(f"| {name} | {n} |")

lines += ["", "## 4. 敏感性：把 UNKNOWN 当作 NEGATIVE 重新计分", "",
          "| method | TP | FP(含原 UNKNOWN) | P | R | F1 |", "|---|---|---|---|---|---|"]
for name, k in methods:
    tp = fp = fn = 0
    for q in preds:
        pred = preds[q][k]
        tp += len(pred & gold_by_q[q]["POSITIVE"])
        fp += len(pred & (gold_by_q[q]["NEGATIVE"] | gold_by_q[q]["UNKNOWN"]))
        fn += len(gold_by_q[q]["POSITIVE"] - pred)
    p, r, f1 = prf(tp, fp, fn)
    summary[f"sensitivity_unknown_as_neg/{name}"] = {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": r, "f1": f1}
    lines.append(f"| {name} | {tp} | {fp} | {p:.3f} | {r:.3f} | {f1:.3f} |")

lines += ["", "## 5. gold POSITIVE 但两个方法都漏掉的边", ""]
miss = Counter()
for q in preds:
    for e in gold_by_q[q]["POSITIVE"]:
        if e not in preds[q]["fixed_edges"] and e not in preds[q]["literal_edges"]:
            miss[cats[q]] += 1
lines.append("| category | missed by both |")
lines.append("|---|---|")
for cat, n in sorted(miss.items()):
    lines.append(f"| {cat} | {n} |")
lines.append(f"| **total** | **{sum(miss.values())}** |")

(PKG / "analysis_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
(PKG / "analysis_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print("\n".join(lines))
