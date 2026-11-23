"""Build the P1 main and stress query sets from Spider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentdb.query_sets import build_sets, write_jsonl

CATEGORIES = ["projection", "join", "aggregate", "cte", "case"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", default="/data/gx/spider/spider/validation-00000-of-00001.parquet")
    parser.add_argument("--train", default="/data/gx/spider/spider/train-00000-of-00001.parquet")
    parser.add_argument("--db-dir", default="/data/gx/spider/db")
    parser.add_argument("--main-per-category", type=int, default=30)
    parser.add_argument("--stress-per-type", type=int, default=8)
    parser.add_argument("--out-main", default="data/spider_main.jsonl")
    parser.add_argument("--out-stress", default="data/spider_stress.jsonl")
    args = parser.parse_args()

    main_rows, stress_rows, counts = build_sets(
        args.validation, args.db_dir, args.main_per_category, args.stress_per_type
    )
    # Fill missing main categories from train.
    have = {row["category"] for row in main_rows}
    if any(cat not in have for cat in CATEGORIES):
        train_main, train_stress, train_counts = build_sets(
            args.train, args.db_dir, args.main_per_category, args.stress_per_type
        )
        for cat in CATEGORIES:
            current = sum(1 for r in main_rows if r["category"] == cat)
            for row in train_main:
                if row["category"] == cat and current < args.main_per_category:
                    main_rows.append(row)
                    current += 1
        for row in train_stress:
            st = row.get("stress_type")
            current = sum(1 for r in stress_rows if r.get("stress_type") == st)
            if current < args.stress_per_type:
                stress_rows.append(row)
                counts["stress"] += 1
        counts["train_fill"] = train_counts

    write_jsonl(args.out_main, main_rows)
    write_jsonl(args.out_stress, stress_rows)
    summary = {
        "n_main": len(main_rows),
        "n_stress": len(stress_rows),
        "main_by_category": {c: sum(1 for r in main_rows if r["category"] == c) for c in CATEGORIES},
        "stress_by_type": {
            t: sum(1 for r in stress_rows if r.get("stress_type") == t)
            for t in ["empty", "limit", "case_untriggered", "aggregate", "fanout"]
        },
        "build": counts,
    }
    Path("data/query_sets_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
