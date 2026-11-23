#!/usr/bin/env python3
"""Inter-annotator agreement for the value-level lineage sheets (ANNOTATION.md §7).

Edge key = (qid, output_column, source_table, source_column), casefolded.
``NONE`` rows only assert that the whole query has no edges and are not
participating edges themselves.

Conventions reported (documented, because annotations are sparse):
  * union / binary      : every edge of the union; "not listed" counts as non-POSITIVE
  * intersection / binary, 3-class : only edges both annotators listed
  * union / 4-class     : "not listed" is its own ABSENT category

Usage:
    python compute_kappa.py --a annotation_A.csv --b annotation_B.csv [--c ...]
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
from pathlib import Path

DECISIONS = ("POSITIVE", "NEGATIVE", "UNKNOWN")


def load(path: Path) -> tuple[dict[tuple, str], set[str]]:
    edges: dict[tuple, str] = {}
    none_qids: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            qid = (row.get("qid") or "").strip()
            if not qid:
                continue
            out = (row.get("output_column") or "").strip()
            tbl = (row.get("source_table") or "").strip()
            col = (row.get("source_column") or "").strip()
            dec = (row.get("decision") or "").strip().upper()
            if out.upper() == "NONE" or dec == "NONE":
                none_qids.add(qid)
                continue
            if dec not in DECISIONS:
                raise SystemExit(f"{path.name}: bad decision {dec!r} for {qid} {out}")
            key = (qid, out.casefold(), tbl.casefold(), col.casefold())
            if key in edges and edges[key] != dec:
                raise SystemExit(f"{path.name}: conflicting duplicate {key}")
            edges[key] = dec
    return edges, none_qids


def kappa(pairs: list[tuple[str, str]], categories: tuple[str, ...]) -> float:
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in categories)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else float("nan")
    return (po - pe) / (1 - pe)


def confusion(pairs: list[tuple[str, str]], categories: tuple[str, ...]) -> dict:
    m = {a: {b: 0 for b in categories} for a in categories}
    for a, b in pairs:
        m[a][b] += 1
    return m


def compare(na: str, a: dict[tuple, str], nb: str, b: dict[tuple, str]) -> dict:
    union = set(a) | set(b)
    inter = set(a) & set(b)

    bin_union = [("POSITIVE" if a.get(k) == "POSITIVE" else "OTHER",
                  "POSITIVE" if b.get(k) == "POSITIVE" else "OTHER") for k in sorted(union)]
    bin_inter = [("POSITIVE" if a[k] == "POSITIVE" else "OTHER",
                  "POSITIVE" if b[k] == "POSITIVE" else "OTHER") for k in sorted(inter)]
    tri_inter = [(a[k], b[k]) for k in sorted(inter)]
    quad_union = [(a.get(k, "ABSENT"), b.get(k, "ABSENT")) for k in sorted(union)]

    out = {
        "pair": f"{na} vs {nb}",
        "n_a": len(a),
        "n_b": len(b),
        "n_common_listed": len(inter),
        "n_union": len(union),
        "percent_agreement_binary_union": round(
            sum(1 for x, y in bin_union if x == y) / len(bin_union), 4
        ),
        "pabak_binary_union": round(
            2 * sum(1 for x, y in bin_union if x == y) / len(bin_union) - 1, 4
        ),
        "binary_kappa_union": round(kappa(bin_union, ("POSITIVE", "OTHER")), 4),
        "binary_kappa_intersection": round(kappa(bin_inter, ("POSITIVE", "OTHER")), 4),
        "three_class_kappa_intersection": round(kappa(tri_inter, DECISIONS), 4),
        "four_class_kappa_union": round(kappa(quad_union, DECISIONS + ("ABSENT",)), 4),
        "confusion_binary_union": confusion(bin_union, ("POSITIVE", "OTHER")),
        "confusion_three_class_intersection": confusion(tri_inter, DECISIONS),
        "confusion_four_class_union": confusion(quad_union, DECISIONS + ("ABSENT",)),
        "edges_only_a": sorted(
            f"{k[0]} | {k[1]} <- {k[2]}.{k[3]}" for k in union if k in a and k not in b
        ),
        "edges_only_b": sorted(
            f"{k[0]} | {k[1]} <- {k[2]}.{k[3]}" for k in union if k in b and k not in a
        ),
        "decision_disagreements": [
            {
                "edge": f"{k[0]} | {k[1]} <- {k[2]}.{k[3]}",
                na: a[k],
                nb: b[k],
            }
            for k in sorted(inter)
            if a[k] != b[k]
        ],
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--c")
    ap.add_argument("--json-out", default="kappa_report.json")
    args = ap.parse_args()

    files = [("A", Path(args.a)), ("B", Path(args.b))]
    if args.c:
        files.append(("C", Path(args.c)))
    sheets = {name: load(path) for name, path in files}

    pairs = []
    for (na, _), (nb, _) in itertools.combinations(files, 2):
        pairs.append(compare(na, sheets[na][0], nb, sheets[nb][0]))

    report = {
        "files": {name: str(path) for name, path in files},
        "n_queries_with_no_edges": {
            name: sorted(qids) for name, (_, qids) in sheets.items()
        },
        "pairwise": pairs,
        "mean_binary_kappa_union": round(
            sum(p["binary_kappa_union"] for p in pairs) / len(pairs), 4
        ),
        "min_binary_kappa_union": min(p["binary_kappa_union"] for p in pairs),
        "gate": {
            "target_binary_kappa": 0.7,
            "recalibration_threshold": 0.6,
            "pass": min(p["binary_kappa_union"] for p in pairs) >= 0.7,
        },
    }
    Path(args.json_out).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    for p in pairs:
        print(f"== {p['pair']} ==")
        print(f"  edges: A={p['n_a']} B={p['n_b']} common={p['n_common_listed']} union={p['n_union']}")
        print(f"  binary kappa (union)        = {p['binary_kappa_union']}")
        print(f"  percent agreement (union)   = {p['percent_agreement_binary_union']}"
              f"   PABAK = {p['pabak_binary_union']}")
        print(f"  binary kappa (intersection) = {p['binary_kappa_intersection']}")
        print(f"  3-class kappa (common)      = {p['three_class_kappa_intersection']}")
        print(f"  4-class kappa (union)       = {p['four_class_kappa_union']}")
        print(f"  disagreements: {len(p['decision_disagreements'])}")
        for d in p["decision_disagreements"]:
            print(f"    - {d['edge']}: {d[p['pair'].split(' vs ')[0]]} vs {d[p['pair'].split(' vs ')[1]]}")
    print(f"\nmean binary kappa = {report['mean_binary_kappa_union']}  gate(>=0.7) = {report['gate']['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
