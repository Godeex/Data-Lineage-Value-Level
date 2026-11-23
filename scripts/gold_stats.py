"""Paired bootstrap statistics for the human-gold evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def paired(a: np.ndarray, b: np.ndarray, n_boot: int = 10000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    diff = a - b
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    p = 2 * min(float((means <= 0).mean()), float((means >= 0).mean()))
    return {
        "n": int(len(diff)),
        "mean_a": float(a.mean()),
        "mean_b": float(b.mean()),
        "mean_diff": float(diff.mean()),
        "ci95": [float(lo), float(hi)],
        "p_two_sided": float(min(1.0, p)),
    }


def main() -> int:
    data = json.loads(Path("results/gold_eval.json").read_text(encoding="utf-8"))
    per = data["per_query"]
    def series(name, key):
        return {r["qid"]: r[key] for r in per[name]}
    pairs = [
        ("machine_reference_vs_static", "machine_reference", "static"),
        ("reference_union_static_vs_machine_reference", "reference_union_static", "machine_reference"),
        ("evolving_vs_fixed_hybrid", "evolving", "fixed_hybrid"),
        ("literal_union_evolving_vs_evolving", "literal_union_evolving", "evolving"),
        ("literal_union_evolving_vs_machine_reference", "literal_union_evolving", "machine_reference"),
        ("literal_union_evolving_vs_reference_union_static", "literal_union_evolving", "reference_union_static"),
        ("literal_union_b10all_vs_b10all", "literal_union_b10all", "oracle_b10_allcell"),
        ("literal_union_reference_vs_reference_union_static", "literal_union_reference", "reference_union_static"),
    ]
    out = {}
    for name, a_name, b_name in pairs:
        a_f1, b_f1 = series(a_name, "f1"), series(b_name, "f1")
        a_r, b_r = series(a_name, "recall"), series(b_name, "recall")
        common = sorted(set(a_f1) & set(b_f1))
        out[name] = {
            "f1": paired(np.array([a_f1[q] for q in common]), np.array([b_f1[q] for q in common])),
            "recall": paired(np.array([a_r[q] for q in common]), np.array([b_r[q] for q in common])),
        }
    Path("results/gold_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
