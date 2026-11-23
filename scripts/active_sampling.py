"""Select information-rich queries for a small second annotation round."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import literal_edges

CATEGORY_WEIGHT = {"join": 3.0, "case": 3.0, "cte": 2.0, "aggregate": 1.5, "projection": 0.5}
TARGET = {"join": 10, "case": 8, "cte": 6, "aggregate": 4, "projection": 2}


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default="data/spider_main.jsonl")
    ap.add_argument("--p1", default="results/p1_coverage.jsonl")
    ap.add_argument("--gold-sample", default="annotations/discovery/package/sample_30.jsonl")
    ap.add_argument("--db-dir", default="/data/gx/spider/db")
    ap.add_argument("--out", default="data/active_annotation_candidates.jsonl")
    ap.add_argument("--n", type=int, default=30)
    args = ap.parse_args()

    main_rows = [json.loads(line) for line in Path(args.main).read_text(encoding="utf-8").splitlines()]
    p1 = {json.loads(line)["qid"]: json.loads(line) for line in Path(args.p1).read_text(encoding="utf-8").splitlines()}
    annotated = {json.loads(line)["qid"] for line in Path(args.gold_sample).read_text(encoding="utf-8").splitlines()}

    scored = []
    for row in main_rows:
        qid = row["qid"]
        if qid in annotated or qid not in p1:
            continue
        ref = norm(p1[qid]["ref_edges"])
        static = norm(p1[qid]["static_edges"])
        try:
            tables = load_sqlite_tables(Path(args.db_dir) / f"{row['db_id']}.sqlite", max_rows=30)
            lit = norm(literal_edges({"sql": row["sql"], "tables": tables}, budget=3)["edges"])
        except Exception:
            lit = set()
        reasons = []
        if static - ref:
            reasons.append(f"static_only={len(static - ref)}")
        if lit - ref:
            reasons.append(f"literal_only={len(lit - ref)}")
        if ref - lit:
            reasons.append(f"reference_only={len(ref - lit)}")
        if not ref and static:
            reasons.append("reference_empty_static_nonempty")
        score = (
            3.0 * len(lit - ref)
            + 2.0 * len(static - ref)
            + 1.0 * len(ref - static)
            + CATEGORY_WEIGHT.get(row["category"], 1.0)
        )
        scored.append({
            "qid": qid, "db_id": row["db_id"], "category": row["category"],
            "sql": row["sql"], "question": row.get("question"),
            "score": round(score, 3), "reasons": reasons,
            "n_ref": len(ref), "n_static": len(static), "n_literal": len(lit),
            "suggested_edges": sorted(ref | static | lit),
        })

    by_cat = defaultdict(list)
    for row in scored:
        by_cat[row["category"]].append(row)
    selected = []
    for cat, rows in by_cat.items():
        rows.sort(key=lambda r: (-r["score"], r["qid"]))
        selected.extend(rows[: TARGET.get(cat, 3)])
    selected.sort(key=lambda r: (-r["score"], r["qid"]))
    selected = selected[: args.n]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in selected) + "\n", encoding="utf-8")
    summary = {
        "n_selected": len(selected),
        "by_category": {c: sum(1 for r in selected if r["category"] == c) for c in sorted({r["category"] for r in selected})},
        "mean_score": sum(r["score"] for r in selected) / len(selected) if selected else 0,
        "candidates_total": len(scored),
    }
    Path(args.out).with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
