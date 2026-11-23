#!/usr/bin/env python3
"""Validate one annotation sheet."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

DECISIONS = {"POSITIVE", "NEGATIVE", "UNKNOWN"}
CONFIDENCE = {"1", "2", "3"}
TYPES = {"", "DATA", "CONTROL", "MIXED", "INDIRECT"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    args = ap.parse_args()
    path = Path(args.sheet)

    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    errors, keys = [], []
    for i, row in enumerate(rows, start=2):
        key = (row.get("qid", ""), row.get("output_column", ""),
               row.get("source_table", ""), row.get("source_column", ""))
        keys.append(key)
        d = (row.get("decision") or "").strip().upper()
        c = (row.get("confidence") or "").strip()
        t = (row.get("evidence_type") or "").strip().upper()
        if d not in DECISIONS:
            errors.append(f"line {i}: invalid decision {d!r}")
        if c not in CONFIDENCE:
            errors.append(f"line {i}: confidence must be 1,2,3")
        if t not in TYPES:
            errors.append(f"line {i}: invalid evidence_type {t!r}")

    dup = [k for k, n in Counter(keys).items() if n > 1]
    if dup:
        errors.append(f"{len(dup)} duplicate edge rows")

    print(f"file: {path}")
    print(f"rows: {len(rows)}")
    print(f"decisions: {dict(Counter((r.get('decision') or '').strip().upper() for r in rows))}")
    print(f"confidence: {dict(Counter((r.get('confidence') or '').strip() for r in rows))}")
    print(f"evidence_type: {dict(Counter((r.get('evidence_type') or '').strip().upper() for r in rows))}")
    if errors:
        print("\nERRORS:")
        for e in errors[:50]:
            print(" -", e)
        return 1
    print("OK: sheet is complete and well-formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
