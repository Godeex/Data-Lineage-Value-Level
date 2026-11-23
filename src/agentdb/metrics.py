"""Edge-level metrics with explicit macro aggregation over pipeline scripts."""

from __future__ import annotations

from typing import Iterable

Edge = tuple[str, str, str]


def prf(predicted: Iterable[Edge], gold: Iterable[Edge]) -> dict[str, float]:
    pred = set(predicted)
    gt = set(gold)
    tp = len(pred & gt)
    fp = len(pred - gt)
    fn = len(gt - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
    }


def macro(per_script: list[dict[str, float]], key: str) -> float:
    if not per_script:
        raise ValueError("macro() needs at least one script result")
    return sum(float(row[key]) for row in per_script) / len(per_script)


def coverage(observed: Iterable[Edge], gold: Iterable[Edge]) -> dict[str, float]:
    obs = set(observed)
    gt = set(gold)
    covered = len(obs & gt)
    total = len(gt)
    return {
        "coverage": covered / total if total else 0.0,
        "false_negative_rate": (total - covered) / total if total else 0.0,
        "observed_edges": float(len(obs)),
        "gold_edges": float(total),
    }
