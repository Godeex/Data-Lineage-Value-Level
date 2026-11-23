#!/usr/bin/env python3
"""Compare the two machine suggestions (reference / static) with the adjudicated gold."""
from __future__ import annotations

import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def k(qid, out, tbl, col):
    return (qid, out.casefold(), tbl.casefold(), col.casefold())


queries = [json.loads(l) for l in (PKG / "sample_30.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
gold = {}
for line in (PKG / "gold_edges.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(line)
    for e in rec["edges"]:
        gold[k(rec["qid"], e["output_column"], e["source_table"], e["source_column"])] = e["decision"]

pos = {g for g, d in gold.items() if d == "POSITIVE"}


def score(name, edges):
    return {
        "suggested": len(edges),
        "gold_POSITIVE": len(edges & pos),
        "gold_NEGATIVE": len({e for e in edges if gold.get(e) == "NEGATIVE"}),
        "gold_UNKNOWN": len({e for e in edges if gold.get(e) == "UNKNOWN"}),
        "not_in_gold": len(edges - set(gold)),
        "precision": round(len(edges & pos) / len(edges), 4) if edges else None,
        "recall": round(len(edges & pos) / len(pos), 4) if pos else None,
    }


ref = {k(q["qid"], *e) for q in queries for e in q["reference_edges_suggestion"]}
static_all = {k(q["qid"], *e) for q in queries for e in q["static_edges_suggestion"]}
# static uses positional names for CTE outputs (_col_0 ...) which never match gold names
static_positional = {e for e in static_all if e[1].startswith("_col_")}
static = static_all - static_positional

rows = {
    "reference_edges_suggestion": score("reference", ref),
    "static_edges_suggestion": score("static", static),
    "union(reference, static)": score("union", ref | static),
    "static_positional_naming_unresolved": {
        "edges": len(static_positional),
        "note": "_col_0/_col_1 这类位置式列名无法与 gold 的 avg(age)/max(capacity) 对齐，评测前必须规范化",
    },
}
missing = sorted(pos - ref - static)
rows["gold_POSITIVE_total"] = {"edges": len(pos)}
rows["missed_by_both"] = [
    {"qid": q, "edge": f"{o} <- {t}.{c}"} for q, o, t, c in missing
]
Path(PKG / "machine_reference_report.json").write_text(
    json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

lines = ["# machine suggestions vs gold (POSITIVE 口径)", "",
         "| suggestion | 建议数 | 命中 POS | 命中 UNKNOWN | 命中 NEG | 不在 gold | precision | recall |",
         "|---|---|---|---|---|---|---|---|"]
for name in ("reference_edges_suggestion", "static_edges_suggestion", "union(reference, static)"):
    r = rows[name]
    lines.append(f"| {name} | {r['suggested']} | {r['gold_POSITIVE']} | {r['gold_UNKNOWN']} | "
                 f"{r['gold_NEGATIVE']} | {r['not_in_gold']} | {r['precision']} | {r['recall']} |")
lines += ["", f"gold POSITIVE 总数：{len(pos)}", "", "## 两个机器建议都没给出的 POSITIVE 边", ""]
for m in rows["missed_by_both"]:
    lines.append(f"- {m['qid']}: {m['edge']}")
Path(PKG / "machine_reference_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
