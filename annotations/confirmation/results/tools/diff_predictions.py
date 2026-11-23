"""Diff frozen predictions against the adjudicated gold (post-scoring analysis)."""
import json
from collections import Counter, defaultdict
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def key(o, t, c):
    return (str(o).casefold().strip(), str(t).casefold().strip(), str(c).casefold().strip())


gold = {}
for line in (PKG / "gold_final.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        gold[(r["qid"], *key(r["output_column"], r["source_table"], r["source_column"]))] = r["decision"]

preds = {}
for line in (PKG / "sealed" / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        preds[r["qid"]] = {k: {tuple(x) for x in r[k]} for k in ("fixed_edges", "literal_edges", "union_edges")}

cats = {json.loads(l)["qid"]: json.loads(l)["category"]
        for l in (PKG / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

print("== fixed predictions that hit gold NEGATIVE ==")
for qid, sets in preds.items():
    for e in sorted(sets["fixed_edges"]):
        g = gold.get((qid, *e))
        if g == "NEGATIVE":
            print(f"  {qid} [{cats[qid]}] {e[0]} <- {e[1]}.{e[2]}")

print("\n== literal predictions that hit gold NEGATIVE ==")
n = 0
for qid, sets in preds.items():
    for e in sorted(sets["literal_edges"]):
        if gold.get((qid, *e)) == "NEGATIVE":
            n += 1
            print(f"  {qid} {e[0]} <- {e[1]}.{e[2]}")
print("  count:", n)

print("\n== gold POSITIVE missed by BOTH ==")
by_cat = Counter()
for qid, sets in preds.items():
    for g, d in gold.items():
        if g[0] != qid or d != "POSITIVE":
            continue
        if g[1:] not in sets["fixed_edges"] and g[1:] not in sets["literal_edges"]:
            by_cat[cats[qid]] += 1
            print(f"  {qid} [{cats[qid]}] {g[1]} <- {g[2]}.{g[3]}")
print("  by category:", dict(by_cat))

print("\n== gold UNKNOWN touched by any prediction ==")
u = 0
for qid, sets in preds.items():
    for name in ("fixed_edges", "literal_edges", "union_edges"):
        for e in sets[name]:
            if gold.get((qid, *e)) == "UNKNOWN":
                u += 1
print("  unjudged predictions:", u)
