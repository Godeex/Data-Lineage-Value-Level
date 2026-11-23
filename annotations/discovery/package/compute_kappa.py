#!/usr/bin/env python3
"""Compute agreement and Cohen's kappa for two annotation CSVs.

Usage:
  python compute_kappa.py --a annotation_A.csv --b annotation_B.csv

Expected columns:
  qid, annotator, output_column, source_table, source_column, decision, confidence, note
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

DECISIONS = ("POSITIVE", "NEGATIVE", "UNKNOWN")


def edge_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("qid", "")).strip().casefold(),
        str(row.get("output_column", "")).strip().casefold(),
        str(row.get("source_table", "")).strip().casefold(),
        str(row.get("source_column", "")).strip().casefold(),
    )


def load(path: str) -> dict[tuple, str]:
    out = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            decision = str(row.get("decision", "")).strip().upper()
            if decision not in DECISIONS:
                continue
            out[edge_key(row)] = decision
    return out


def cohen_kappa(a: list[str], b: list[str], categories: tuple[str, ...]) -> dict:
    n = len(a)
    if n == 0:
        return {"n": 0, "kappa": None, "observed_agreement": None, "expected_agreement": None}
    agree = sum(1 for x, y in zip(a, b) if x == y)
    po = agree / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in categories)
    kappa = (po - pe) / (1 - pe) if pe < 1 else None
    return {
        "n": n,
        "observed_agreement": round(po, 4),
        "expected_agreement": round(pe, 4),
        "kappa": round(kappa, 4) if kappa is not None else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", default="kappa_report.json")
    args = ap.parse_args()

    a = load(args.a)
    b = load(args.b)
    common = sorted(set(a) & set(b))
    union = sorted(set(a) | set(b))
    a_only = sorted(set(a) - set(b))
    b_only = sorted(set(b) - set(a))

    a_pos = [1 if a[k] == "POSITIVE" else 0 for k in common]
    b_pos = [1 if b[k] == "POSITIVE" else 0 for k in common]
    binary = cohen_kappa(a_pos, b_pos, (0, 1))
    three = cohen_kappa([a[k] for k in common], [b[k] for k in common], DECISIONS)

    # Union-level agreement: missing from one side is a separate category.
    union_a = [a.get(k, "MISSING") for k in union]
    union_b = [b.get(k, "MISSING") for k in union]
    union_kappa = cohen_kappa(union_a, union_b, DECISIONS + ("MISSING",))

    report = {
        "n_a": len(a),
        "n_b": len(b),
        "n_common": len(common),
        "n_union": len(union),
        "a_only": len(a_only),
        "b_only": len(b_only),
        "binary_kappa_positive_vs_other": binary,
        "three_class_kappa": three,
        "union_kappa_with_missing": union_kappa,
        "a_only_edges": [" | ".join(k) for k in a_only],
        "b_only_edges": [" | ".join(k) for k in b_only],
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
