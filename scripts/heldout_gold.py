"""Strict held-out experiment: learn on non-gold queries, evaluate on 30 human gold."""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from agentdb.evolve import CANDIDATES, eval_policy
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

STRUCTURAL_RE = re.compile(r"\b(WHERE|CASE|GROUP\s+BY|ORDER\s+BY|HAVING)\b", re.I)


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def metrics(pred, pos, neg, unk):
    tp = len(pred & pos)
    fp = len(pred & neg)
    fn = len(pos - pred)
    outside = len(pred - pos - neg - unk)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "outside": outside,
            "precision": precision, "recall": recall, "f1": f1}


def output_names(db_path: Path, sql: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(sql)
        return [d[0] for d in (cur.description or [])]
    except Exception:
        return []
    finally:
        conn.close()


def norm_named(edges, names):
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        m = re.fullmatch(r"_col_(\d+)", o)
        if m and int(m.group(1)) < len(names):
            o = str(names[int(m.group(1))]).casefold().strip()
        out.add((o, str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def split_pool(pool: list[dict], gold_sql_keys: set[str], seed: int = 42):
    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for r in pool:
        if r["sql"].strip().casefold() in gold_sql_keys:
            continue
        by_cat[r["category"]].append(r)
    splits = {"train": [], "val": [], "regression": []}
    for cat, rows in by_cat.items():
        groups = defaultdict(list)
        for r in rows:
            groups[r["sql"].strip().casefold()].append(r)
        keys = sorted(groups)
        rng.shuffle(keys)
        n = len(keys)
        nt = max(1, int(0.6 * n))
        nv = max(1, int(0.2 * n))
        for k in keys[:nt]:
            splits["train"].extend(groups[k])
        for k in keys[nt : nt + nv]:
            splits["val"].extend(groups[k])
        for k in keys[nt + nv :]:
            splits["regression"].extend(groups[k])
    return splits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default="data/spider_main.jsonl")
    ap.add_argument("--p1", default="results/p1_coverage.jsonl")
    ap.add_argument("--gold", default="annotations/discovery/results/gold_edges.jsonl")
    ap.add_argument("--db-dir", default="/data/gx/spider/db")
    ap.add_argument("--out", default="results/heldout_gold.json")
    args = ap.parse_args()

    main_rows = [json.loads(line) for line in Path(args.main).read_text(encoding="utf-8").splitlines()]
    p1 = {json.loads(line)["qid"]: json.loads(line) for line in Path(args.p1).read_text(encoding="utf-8").splitlines()}
    gold = {}
    for line in Path(args.gold).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        gold[row["qid"]] = {
            "POSITIVE": {(e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()) for e in row["edges"] if e["decision"] == "POSITIVE"},
            "NEGATIVE": {(e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()) for e in row["edges"] if e["decision"] == "NEGATIVE"},
            "UNKNOWN": {(e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()) for e in row["edges"] if e["decision"] == "UNKNOWN"},
        }
    gold_qids = set(gold)
    gold_sql_keys = {r["sql"].strip().casefold() for r in main_rows if r["qid"] in gold_qids}
    pool = []
    for r in main_rows:
        if r["qid"] in gold_qids or r["qid"] not in p1:
            continue
        r = dict(r)
        r["ref_edges"] = p1[r["qid"]]["ref_edges"]
        r["static_edges"] = p1[r["qid"]]["static_edges"]
        pool.append(r)
    splits = split_pool(pool, gold_sql_keys)
    print({k: len(v) for k, v in splits.items()})

    learned = {}
    selection = {}
    for cat in sorted({r["category"] for r in splits["train"]}):
        train_cat = [r for r in splits["train"] if r["category"] == cat]
        val_cat = [r for r in splits["val"] if r["category"] == cat]
        best = None
        for cand in CANDIDATES:
            tr = eval_policy(train_cat, {"__default__": cand}, args.db_dir, include_static=True)
            va = eval_policy(val_cat, {"__default__": cand}, args.db_dir, include_static=True) if val_cat else tr
            score = (va["macro_f1"], -va["mean_executions"])
            if best is None or score > best[0]:
                best = (score, cand, tr, va)
        learned[cat] = best[1]
        selection[cat] = {"policy": best[1], "train_f1": best[2]["macro_f1"], "val_f1": best[3]["macro_f1"]}
    print("learned", json.dumps(learned, ensure_ascii=False))

    per_method = defaultdict(list)
    for qid, g in gold.items():
        row = next(r for r in main_rows if r["qid"] == qid)
        db_path = Path(args.db_dir) / f"{row['db_id']}.sqlite"
        names = output_names(db_path, row["sql"])
        static = norm_named(p1[qid]["static_edges"], names)
        ref = norm_named(p1[qid]["ref_edges"], names)
        tables = load_sqlite_tables(db_path, max_rows=30)
        script = {"sql": row["sql"], "tables": tables}
        lit_out = literal_edges(script, budget=3)
        lit = norm_named(lit_out["edges"], names)
        policy = learned.get(row["category"], CANDIDATES[1])
        evo_out = limited_edges(script, policy["families"], policy["budget"])
        evo = norm_named(evo_out["edges"], names)
        structural = bool(STRUCTURAL_RE.search(row["sql"]))
        preds = {
            "static": (static, 0),
            "machine_reference": (ref, p1[qid]["ref_executions"]),
            "fixed_hybrid": (static | norm_named(limited_edges(script, ["CELL_VALUE"], 3)["edges"], names), 60),
            "evolving": (static | evo, evo_out["executions"]),
            "literal": (lit, lit_out["executions"]),
            "literal_union_evolving": (static | evo | lit, evo_out["executions"] + lit_out["executions"]),
            "predicate_aware": (static | evo | (lit if structural else set()), evo_out["executions"] + (lit_out["executions"] if structural else 0)),
        }
        for name, (pred, cost) in preds.items():
            m = metrics(pred, g["POSITIVE"], g["NEGATIVE"], g["UNKNOWN"])
            m.update({"qid": qid, "category": row["category"], "method": name, "executions": cost})
            per_method[name].append(m)

    summary = {}
    for name, recs in per_method.items():
        n = len(recs)
        summary[name] = {
            "n": n,
            "micro_tp": sum(r["tp"] for r in recs),
            "micro_fp": sum(r["fp"] for r in recs),
            "micro_fn": sum(r["fn"] for r in recs),
            "micro_outside": sum(r["outside"] for r in recs),
            "macro_f1": sum(r["f1"] for r in recs) / n,
            "mean_executions": sum(r["executions"] for r in recs) / n,
        }
    Path(args.out).write_text(json.dumps({"splits": {k: len(v) for k, v in splits.items()},
                                          "learned_policies": learned, "selection": selection,
                                          "summary": summary, "per_query": dict(per_method)},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
