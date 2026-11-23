#!/usr/bin/env python3
"""Cross-check the adjudicated gold against the perturbation evidence.

POSITIVE edges must have a witness; NEGATIVE/UNKNOWN edges must not have one in
the probe run (a witness there would contradict the adjudication).
"""
from __future__ import annotations

import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
ev = json.loads((PKG / "tools" / "evidence.json").read_text(encoding="utf-8"))

witness = set()
for qid, info in ev.items():
    for e in info["edges"].values():
        witness.add((qid, e["output_column"].casefold(), e["source_table"].casefold(),
                     e["source_column"].casefold()))

bad_pos, bad_abstain, ok = [], [], 0
for line in (PKG / "gold_edges.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(line)
    for e in rec["edges"]:
        key = (rec["qid"], e["output_column"].casefold(), e["source_table"].casefold(),
               e["source_column"].casefold())
        has = key in witness
        if e["decision"] == "POSITIVE" and not has:
            bad_pos.append(key)
        elif e["decision"] != "POSITIVE" and has:
            bad_abstain.append((key, e["decision"]))
        else:
            ok += 1

print(f"consistent: {ok}")
print(f"POSITIVE without witness: {len(bad_pos)}")
for k in bad_pos:
    print("   ", k)
print(f"UNKNOWN/NEGATIVE with witness: {len(bad_abstain)}")
for k, d in bad_abstain:
    print("   ", d, k)
print(f"witnessed edges in probe: {len(witness)}")
