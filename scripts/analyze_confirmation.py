"""Blind-spot replication and transition analysis on the 42-template confirmation set."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "results/confirmation_gold_final.jsonl"
QUERIES = ROOT / "results/confirmation_queries.jsonl"
P1 = ROOT / "results/p1_coverage.jsonl"
PREDS = ROOT / "annotations/confirmation/results/sealed/predictions.jsonl"


def norm(edges):
    out = set()
    for e in edges:
        if isinstance(e, dict):
            out.add((str(e["output_column"]).casefold().strip(), str(e["source_table"]).casefold().strip(), str(e["source_column"]).casefold().strip()))
        else:
            o, t, c = e
            out.add((str(o).casefold().strip(), str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def clause_sets(sql: str):
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return set(), set(), set()
    control, select, groupcase = set(), set(), set()
    for node in tree.find_all(exp.Where, exp.Having, exp.Join):
        for c in node.find_all(exp.Column):
            control.add(c.name.casefold())
    # ORDER BY only with LIMIT/OFFSET
    if tree.find(exp.Limit) or tree.find(exp.Offset):
        for node in tree.find_all(exp.Order):
            for c in node.find_all(exp.Column):
                control.add(c.name.casefold())
    for node in tree.find_all(exp.Group):
        for c in node.find_all(exp.Column):
            control.add(c.name.casefold())
            groupcase.add(c.name.casefold())
    for node in tree.find_all(exp.Case):
        for c in node.find_all(exp.Column):
            control.add(c.name.casefold())
            groupcase.add(c.name.casefold())
    for node in tree.find_all(exp.Select):
        for proj in node.expressions:
            for c in proj.find_all(exp.Column):
                select.add(c.name.casefold())
    return control, select, groupcase


def main() -> int:
    gold = defaultdict(lambda: {"POSITIVE": set(), "NEGATIVE": set(), "UNKNOWN": set()})
    for line in GOLD.read_text().splitlines():
        r = json.loads(line)
        d = r["decision"].upper()
        if d not in gold[r["qid"]]:
            d = "UNKNOWN"
        gold[r["qid"]][d].add((r["output_column"].casefold(), r["source_table"].casefold(), r["source_column"].casefold()))
    queries = {json.loads(l)["qid"]: json.loads(l) for l in QUERIES.read_text().splitlines()}
    p1 = {json.loads(l)["qid"]: json.loads(l) for l in P1.read_text().splitlines()}
    preds = {json.loads(l)["qid"]: json.loads(l) for l in PREDS.read_text().splitlines()}

    per_q = []
    missed = []
    trans = Counter()
    trans_types = Counter()
    by_type = defaultdict(Counter)
    by_cat = defaultdict(lambda: Counter())
    for qid, q in queries.items():
        pg = gold[qid]
        if not pg["POSITIVE"]:
            continue
        ref = norm(p1[qid]["ref_edges"])
        ctrl, sel, groupcase = clause_sets(q["sql"])
        types = {}
        for e in pg["POSITIVE"]:
            col = e[2]
            if col in ctrl and col in sel:
                types[e] = "MIXED"
            elif col in ctrl:
                types[e] = "CONTROL"
            elif col in sel:
                types[e] = "DATA"
            else:
                types[e] = "INDIRECT"
        tp = len(pg["POSITIVE"] & ref)
        fn = pg["POSITIVE"] - ref
        per_q.append({"qid": qid, "category": q["category"], "pos": len(pg["POSITIVE"]), "ref_tp": tp, "ref_fn": len(fn)})
        by_cat[q["category"]]["pos"] += len(pg["POSITIVE"])
        by_cat[q["category"]]["ref_tp"] += tp
        by_cat[q["category"]]["ref_fn"] += len(fn)
        for e in fn:
            typ = types[e]
            col = e[2]
            if col in groupcase and "case" in q["sql"].casefold():
                bucket = "CASE"
            elif col in groupcase:
                bucket = "GROUP BY"
            elif col in ctrl:
                bucket = "WHERE/HAVING/JOIN"
            else:
                bucket = "other"
            by_type[typ][bucket] += 1
            missed.append({"qid": qid, "category": q["category"], "edge": list(e), "type": typ, "bucket": bucket})

        fixed = {tuple(x) for x in preds[qid]["fixed_edges"]}
        lit = {tuple(x) for x in preds[qid]["literal_edges"]}
        for e in pg["POSITIVE"]:
            a, b = e in fixed, e in lit
            key = ("TP" if a else "FN") + "_" + ("TP" if b else "FN")
            trans[key] += 1
            if key in ("FN_TP", "TP_FN"):
                trans_types[(key, types[e])] += 1

    payload = {
        "n_queries": len(per_q),
        "positives": sum(r["pos"] for r in per_q),
        "machine_tp": sum(r["ref_tp"] for r in per_q),
        "machine_fn": sum(r["ref_fn"] for r in per_q),
        "by_category": {k: dict(v) for k, v in by_cat.items()},
        "missed_by_type_bucket": {t: dict(c) for t, c in by_type.items()},
        "transitions": dict(trans),
        "transition_types": {f"{k[0]}/{k[1]}": v for k, v in sorted(trans_types.items())},
        "missed_edges": missed,
    }
    (ROOT / "results/confirmation_analysis.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in payload.items() if k != "missed_edges"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
