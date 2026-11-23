#!/usr/bin/env python3
"""Compute pairwise agreement and a majority gold from three annotation sheets."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

DECISIONS = ("POSITIVE", "NEGATIVE", "UNKNOWN")


def key(row):
    return (row["qid"].strip().casefold(), row["output_column"].strip().casefold(),
            row["source_table"].strip().casefold(), row["source_column"].strip().casefold())


def load(path):
    out = {}
    for row in csv.DictReader(Path(path).open(encoding="utf-8-sig", newline="")):
        d = (row.get("decision") or "").strip().upper()
        if d in DECISIONS:
            out[key(row)] = d
    return out


def kappa(a, b, cats):
    n = len(a)
    if not n:
        return {"n": 0, "kappa": None, "agreement": None}
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] / n * cb[c] / n for c in cats)
    return {"n": n, "agreement": round(po, 4), "kappa": round((po - pe) / (1 - pe), 4) if pe < 1 else None}


def pair(a, b):
    common = sorted(set(a) & set(b))
    pos_a = [1 if a[k] == "POSITIVE" else 0 for k in common]
    pos_b = [1 if b[k] == "POSITIVE" else 0 for k in common]
    return {
        "n_common": len(common),
        "binary_positive_vs_other": kappa(pos_a, pos_b, (0, 1)),
        "three_class": kappa([a[k] for k in common], [b[k] for k in common], DECISIONS),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--c", required=True)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()
    out = Path(args.out_dir)
    a, b, c = load(args.a), load(args.b), load(args.c)

    report = {"pairwise": {"A-B": pair(a, b), "A-C": pair(a, c), "B-C": pair(b, c)}}
    report["pairwise_mean_binary_kappa"] = round(
        sum(report["pairwise"][p]["binary_positive_vs_other"]["kappa"] or 0 for p in ("A-B", "A-C", "B-C")) / 3, 4
    )

    keys = sorted(set(a) | set(b) | set(c))
    gold, disputed = [], []
    for k in keys:
        votes = [d[k] for d in (a, b, c) if k in d]
        count = Counter(votes)
        top, n = count.most_common(1)[0]
        rec = {"qid": k[0], "output_column": k[1], "source_table": k[2], "source_column": k[3]}
        if n >= 2:
            rec["decision"] = top
            rec["votes"] = votes
            gold.append(rec)
        else:
            rec["decision"] = "DISPUTED"
            rec["votes"] = votes
            disputed.append(rec)

    (out / "agreement_report.json").write_text(json.dumps(report, indent=1))
    with (out / "gold_majority.jsonl").open("w") as fh:
        for rec in gold:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with (out / "disputed_edges.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "output_column", "source_table", "source_column", "votes", "adjudicated_decision"])
        for rec in disputed:
            w.writerow([rec["qid"], rec["output_column"], rec["source_table"], rec["source_column"],
                        "|".join(rec["votes"]), ""])
    print(json.dumps(report, indent=1))
    print(f"majority edges: {len(gold)}; disputed: {len(disputed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
