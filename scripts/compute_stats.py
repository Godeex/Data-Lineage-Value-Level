"""Bootstrap CIs and paired tests for P1/P2/P3 (numpy only)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def bootstrap_paired(a: np.ndarray, b: np.ndarray, n_boot: int = 10000, seed: int = 42):
    rng = np.random.default_rng(seed)
    diff = a - b
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    frac_le = float((means <= 0).mean())
    frac_ge = float((means >= 0).mean())
    p = 2 * min(frac_le, frac_ge)
    return {
        "n": int(len(diff)),
        "mean_a": float(a.mean()),
        "mean_b": float(b.mean()),
        "mean_diff": float(diff.mean()),
        "ci95": [float(lo), float(hi)],
        "p_two_sided": float(min(1.0, p)),
    }


def main() -> int:
    out = {}
    # P1: b3_cell vs b10_allcell coverage
    p1 = [json.loads(line) for line in Path("results/p1_coverage.jsonl").read_text(encoding="utf-8").splitlines()]
    main_rows = [r for r in p1 if r.get("stress_type") is None and r["n_ref"] > 0]
    a = np.array([r["policies"]["b10_allcell"]["coverage"] for r in main_rows], dtype=float)
    b = np.array([r["policies"]["b3_cell"]["coverage"] for r in main_rows], dtype=float)
    out["p1_main_coverage_b10all_vs_b3cell"] = bootstrap_paired(a, b)
    by_cat = {}
    for cat in sorted({r["category"] for r in main_rows}):
        rows = [r for r in main_rows if r["category"] == cat]
        aa = np.array([r["policies"]["b10_allcell"]["coverage"] for r in rows], dtype=float)
        bb = np.array([r["policies"]["b3_cell"]["coverage"] for r in rows], dtype=float)
        by_cat[cat] = bootstrap_paired(aa, bb)
    out["p1_by_category"] = by_cat

    # P2: evolving vs fixed hybrid on test/val/regression
    p2 = json.loads(Path("results/p2_evolution.json").read_text(encoding="utf-8"))
    p2_stats = {}
    for split in ("test", "val", "regression"):
        fixed = {r["qid"]: r for r in p2[split]["fixed_hybrid"]["per_query"]}
        evo = {r["qid"]: r for r in p2[split]["evolving"]["per_query"]}
        common = sorted(set(fixed) & set(evo))
        aa = np.array([evo[q]["f1"] for q in common], dtype=float)
        bb = np.array([fixed[q]["f1"] for q in common], dtype=float)
        p2_stats[split] = bootstrap_paired(aa, bb)
        p2_stats[split]["mean_exec_evo"] = p2[split]["evolving"]["mean_executions"]
        p2_stats[split]["mean_exec_fixed"] = p2[split]["fixed_hybrid"]["mean_executions"]
    out["p2_evolving_vs_fixed"] = p2_stats

    # P3 descriptive
    p3 = json.loads(Path("results/p3_dbt.json").read_text(encoding="utf-8"))
    f1 = np.array([r.get("expanded_static_f1", 0.0) for r in p3], dtype=float)
    base = np.array([r.get("base_coverage") or 0.0 for r in p3], dtype=float)
    allc = np.array([r.get("allcell_coverage") or 0.0 for r in p3], dtype=float)
    out["p3"] = {
        "n": int(len(p3)),
        "raw_static_errors": int(sum(1 for r in p3 if r["raw_static_status"] != "parsed")),
        "mean_expanded_static_f1": float(f1.mean()),
        "mean_base_coverage": float(base.mean()),
        "mean_allcell_coverage": float(allc.mean()),
    }
    Path("results/stats_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
