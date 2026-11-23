"""P2: four baselines + category-aware policy evolution under train/val/test splits."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges

CANDIDATES = [
    {"families": ["CELL_VALUE"], "budget": 1},
    {"families": ["CELL_VALUE"], "budget": 3},
    {"families": ["CELL_VALUE"], "budget": 5},
    {"families": ["CELL_VALUE"], "budget": 10},
    {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 1},
    {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 3},
    {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 5},
    {"families": ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], "budget": 10},
]
BASE_POLICY = {"families": ["CELL_VALUE"], "budget": 3}


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def prf(pred, gold):
    pred, gold = set(pred), set(gold)
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def split_by_db(rows: list[dict[str, Any]], seed: int = 42) -> dict[str, list[dict[str, Any]]]:
    db_ids = sorted({row["db_id"] for row in rows})
    rng = random.Random(seed)
    rng.shuffle(db_ids)
    n = len(db_ids)
    n_train = max(1, int(0.6 * n))
    n_val = max(1, int(0.2 * n))
    train_dbs = set(db_ids[:n_train])
    val_dbs = set(db_ids[n_train : n_train + n_val])
    test_dbs = set(db_ids[n_train + n_val :])
    # Regression set: the first half of test DB queries (non-overlapping with test final? use test as final only)
    splits = {"train": [], "val": [], "test": []}
    for row in rows:
        if row["db_id"] in train_dbs:
            splits["train"].append(row)
        elif row["db_id"] in val_dbs:
            splits["val"].append(row)
        elif row["db_id"] in test_dbs:
            splits["test"].append(row)
    return splits


def _load_tables(db_id: str, db_dir: str, max_rows: int) -> dict[str, Any]:
    return load_sqlite_tables(Path(db_dir) / f"{db_id}.sqlite", max_rows=max_rows)


def eval_policy(
    rows: list[dict[str, Any]],
    policy_by_category: dict[str, dict[str, Any]],
    db_dir: str,
    max_rows: int = 30,
    cache: dict | None = None,
    include_static: bool = False,
) -> dict[str, Any]:
    cache = cache if cache is not None else {}
    totals = defaultdict(float)
    per_category = defaultdict(lambda: defaultdict(float))
    per_query = []
    n = 0
    for row in rows:
        ref = norm(row["ref_edges"])
        if not ref:
            continue
        cat = row.get("category", "unknown")
        policy = policy_by_category.get(cat, policy_by_category.get("__default__", BASE_POLICY))
        key = (row["qid"], tuple(policy["families"]), policy["budget"])
        if key not in cache:
            tables = _load_tables(row["db_id"], db_dir, max_rows)
            obs = limited_edges({"sql": row["sql"], "tables": tables}, policy["families"], policy["budget"])
            cache[key] = {"edges": norm(obs["edges"]), "executions": obs["executions"]}
        obs = cache[key]
        pred = set(obs["edges"])
        if include_static:
            pred |= norm(row.get("static_edges", []))
        precision, recall, f1 = prf(pred, ref)
        fn = (len(ref - pred) / len(ref)) if ref else 0.0
        n += 1
        totals["f1"] += f1
        totals["precision"] += precision
        totals["recall"] += recall
        totals["fn"] += fn
        totals["executions"] += obs["executions"]
        totals["abstain"] += 1 if (not pred and ref) else 0
        per_category[cat]["f1"] += f1
        per_category[cat]["fn"] += fn
        per_category[cat]["n"] += 1
        per_category[cat]["executions"] += obs["executions"]
        per_query.append({"qid": row["qid"], "category": cat, "f1": f1, "fn": fn,
                          "precision": precision, "recall": recall, "executions": obs["executions"]})
    out = {
        "n_queries": n,
        "macro_f1": totals["f1"] / n if n else 0.0,
        "macro_precision": totals["precision"] / n if n else 0.0,
        "macro_recall": totals["recall"] / n if n else 0.0,
        "mean_fn_rate": totals["fn"] / n if n else 0.0,
        "abstention_rate": totals["abstain"] / n if n else 0.0,
        "mean_executions": totals["executions"] / n if n else 0.0,
        "per_category": {
            cat: {
                "n": int(v["n"]),
                "macro_f1": v["f1"] / v["n"] if v["n"] else 0.0,
                "mean_fn_rate": v["fn"] / v["n"] if v["n"] else 0.0,
                "mean_executions": v["executions"] / v["n"] if v["n"] else 0.0,
            }
            for cat, v in per_category.items()
        },
        "per_query": per_query,
    }
    return out


def evaluate_static(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = defaultdict(float)
    per_category = defaultdict(lambda: defaultdict(float))
    per_query = []
    n = 0
    for row in rows:
        ref = norm(row["ref_edges"])
        if not ref:
            continue
        static = norm(row["static_edges"])
        precision, recall, f1 = prf(static, ref)
        cat = row.get("category", "unknown")
        n += 1
        totals["f1"] += f1
        totals["precision"] += precision
        totals["recall"] += recall
        totals["executions"] += 0
        per_category[cat]["f1"] += f1
        per_category[cat]["n"] += 1
        per_query.append({"qid": row["qid"], "category": cat, "f1": f1,
                          "precision": precision, "recall": recall, "executions": 0})
    return {
        "n_queries": n,
        "macro_f1": totals["f1"] / n if n else 0.0,
        "macro_precision": totals["precision"] / n if n else 0.0,
        "macro_recall": totals["recall"] / n if n else 0.0,
        "mean_executions": 0.0,
        "per_category": {
            cat: {"n": int(v["n"]), "macro_f1": v["f1"] / v["n"] if v["n"] else 0.0}
            for cat, v in per_category.items()
        },
        "per_query": per_query,
    }


def fixed_hybrid(rows: list[dict[str, Any]], db_dir: str, max_rows: int = 30) -> dict[str, Any]:
    totals = defaultdict(float)
    per_query = []
    n = 0
    for row in rows:
        ref = norm(row["ref_edges"])
        if not ref:
            continue
        tables = _load_tables(row["db_id"], db_dir, max_rows)
        obs = limited_edges({"sql": row["sql"], "tables": tables}, BASE_POLICY["families"], BASE_POLICY["budget"])
        hybrid = norm(row["static_edges"]) | norm(obs["edges"])
        precision, recall, f1 = prf(hybrid, ref)
        n += 1
        totals["f1"] += f1
        totals["precision"] += precision
        totals["recall"] += recall
        totals["executions"] += obs["executions"]
        per_query.append({"qid": row["qid"], "category": row.get("category"), "f1": f1,
                          "precision": precision, "recall": recall, "executions": obs["executions"]})
    return {
        "n_queries": n,
        "macro_f1": totals["f1"] / n if n else 0.0,
        "macro_precision": totals["precision"] / n if n else 0.0,
        "macro_recall": totals["recall"] / n if n else 0.0,
        "mean_executions": totals["executions"] / n if n else 0.0,
        "per_query": per_query,
    }


def learn_policy(train_rows: list[dict[str, Any]], db_dir: str, max_rows: int = 30) -> tuple[dict, dict]:
    categories = sorted({r.get("category", "unknown") for r in train_rows})
    chosen = {}
    details = {}
    cache = {}
    for cat in categories:
        cat_rows = [r for r in train_rows if r.get("category", "unknown") == cat]
        best = None
        for cand in CANDIDATES:
            res = eval_policy(cat_rows, {"__default__": cand}, db_dir, max_rows, cache, include_static=True)
            score = (res["macro_f1"], -res["mean_executions"])
            if best is None or score > best[0]:
                best = (score, cand, res)
        chosen[cat] = best[1]
        details[cat] = {"policy": best[1], "train": best[2]}
    return chosen, details
