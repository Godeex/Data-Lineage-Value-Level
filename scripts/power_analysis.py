"""Bootstrap power projection for the human-gold comparisons (queries as units)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PAIRS = [
    ("literal_union_evolving_vs_machine_reference", "literal_union_evolving", "machine_reference"),
    ("evolving_vs_fixed_hybrid", "evolving", "fixed_hybrid"),
    ("literal_union_evolving_vs_reference_union_static", "literal_union_evolving", "reference_union_static"),
]


def signflip_p(diffs: np.ndarray, rng: np.random.Generator, n_perm: int = 400) -> float:
    obs = abs(float(diffs.mean()))
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(diffs)))
    means = np.abs((diffs[None, :] * signs).mean(axis=1))
    return float((means >= obs).mean())


def main() -> int:
    data = json.loads(Path("results/gold_eval.json").read_text(encoding="utf-8"))["per_query"]
    def series(name):
        return {r["qid"]: r["f1"] for r in data[name]}

    out = {}
    rng = np.random.default_rng(42)
    for label, a_name, b_name in PAIRS:
        a, b = series(a_name), series(b_name)
        qids = sorted(set(a) & set(b))
        diffs = np.array([a[q] - b[q] for q in qids], dtype=float)
        observed = {
            "n": int(len(diffs)),
            "mean_diff": float(diffs.mean()),
            "sd": float(diffs.std(ddof=1)),
            "cohen_dz": float(diffs.mean() / diffs.std(ddof=1)) if diffs.std(ddof=1) else None,
            "p_signflip": signflip_p(diffs, rng),
        }
        power = {}
        for n in (30, 50, 80, 100):
            hits = 0
            sims = 500
            for _ in range(sims):
                sample = rng.choice(diffs, size=n, replace=True)
                if signflip_p(sample, rng, n_perm=200) < 0.05:
                    hits += 1
            power[str(n)] = hits / sims
        out[label] = {"observed": observed, "power_projection": power}
    Path("results/power_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
