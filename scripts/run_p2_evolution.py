"""P2: evolve category-aware perturbation policies and compare four baselines."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from agentdb.evolve import (
    BASE_POLICY,
    CANDIDATES,
    eval_policy,
    evaluate_static,
    fixed_hybrid,
    learn_policy,
    norm,
    prf,
)


def load_rows(main_path: str, p1_path: str) -> list[dict]:
    main = [json.loads(line) for line in Path(main_path).read_text(encoding="utf-8").splitlines()]
    p1 = {json.loads(line)["qid"]: json.loads(line) for line in Path(p1_path).read_text(encoding="utf-8").splitlines()}
    rows = []
    for row in main:
        rec = p1.get(row["qid"])
        if not rec:
            continue
        row = dict(row)
        row["ref_edges"] = rec["ref_edges"]
        row["static_edges"] = rec["static_edges"]
        rows.append(row)
    return rows


def split_four(rows: list[dict], seed: int = 42) -> dict[str, list[dict]]:
    """Stratified query-level split by category (50/20/15/15)."""
    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for row in rows:
        by_cat[row.get("category", "unknown")].append(row)
    out = defaultdict(list)
    for cat, cat_rows in by_cat.items():
        rng.shuffle(cat_rows)
        n = len(cat_rows)
        n_train = max(1, int(0.5 * n))
        n_val = max(1, int(0.2 * n))
        n_test = max(1, int(0.15 * n))
        out["train"].extend(cat_rows[:n_train])
        out["val"].extend(cat_rows[n_train : n_train + n_val])
        out["test"].extend(cat_rows[n_train + n_val : n_train + n_val + n_test])
        out["regression"].extend(cat_rows[n_train + n_val + n_test :])
    return dict(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", default="data/spider_main.jsonl")
    parser.add_argument("--p1", default="results/p1_coverage.jsonl")
    parser.add_argument("--db-dir", default="/data/gx/spider/db")
    parser.add_argument("--out", default="results/p2_evolution.json")
    args = parser.parse_args()

    rows = load_rows(args.main, args.p1)
    splits = split_four(rows)
    print({k: len(v) for k, v in splits.items()})

    learned, details = learn_policy(splits["train"], args.db_dir)
    print("learned policies:", json.dumps(learned, ensure_ascii=False))

    base_policy = {"__default__": BASE_POLICY}
    results = {
        "splits": {k: len(v) for k, v in splits.items()},
        "learned_policies": learned,
        "learn_details": details,
        "test": {
            "static": evaluate_static(splits["test"]),
            "oracle_only": eval_policy(splits["test"], base_policy, args.db_dir),
            "fixed_hybrid": fixed_hybrid(splits["test"], args.db_dir),
            "evolving": eval_policy(splits["test"], learned, args.db_dir, include_static=True),
        },
        "val": {
            "oracle_only": eval_policy(splits["val"], base_policy, args.db_dir),
            "fixed_hybrid": fixed_hybrid(splits["val"], args.db_dir),
            "evolving": eval_policy(splits["val"], learned, args.db_dir, include_static=True),
        },
        "regression": {
            "fixed_hybrid": fixed_hybrid(splits["regression"], args.db_dir),
            "evolving": eval_policy(splits["regression"], learned, args.db_dir, include_static=True),
        },
    }
    # Acceptance rule: evolving must not degrade regression F1 by more than 2pp.
    reg_gap = results["regression"]["fixed_hybrid"]["macro_f1"] - results["regression"]["evolving"]["macro_f1"]
    results["regression_gap"] = reg_gap
    results["accepted"] = reg_gap <= 0.02
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {
        "macro_f1": v["macro_f1"], "mean_fn_rate": v.get("mean_fn_rate"),
        "mean_executions": v.get("mean_executions"),
    } for k, v in results["test"].items()}, ensure_ascii=False, indent=1))
    print("accepted:", results["accepted"], "reg_gap:", round(reg_gap, 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
