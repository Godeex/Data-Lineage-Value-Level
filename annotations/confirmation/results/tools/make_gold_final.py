#!/usr/bin/env python3
"""Merge majority gold + adjudicated disputes into gold_final.jsonl (all 492 edges)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
ADJ = {
    ("validation-00043", "count(*)", "stadium", "capacity"): "UNKNOWN",
}
REASON = {
    ("validation-00043", "count(*)", "stadium", "capacity"):
        "A 主张语义上 capacity 决定子查询返回的 id；C 主张文本/数值比较规则下不可能命中；本实例无见证，按“路径存在但被类型不一致遮蔽”判 UNKNOWN",
}


def main() -> int:
    rows = [json.loads(l) for l in (PKG / "gold_majority.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = set()
    gold = []
    for r in rows:
        key = (r["qid"], r["output_column"], r["source_table"], r["source_column"])
        seen.add(key)
        gold.append({k: r[k] for k in ("qid", "output_column", "source_table", "source_column", "decision")})

    disputed = list(csv.DictReader((PKG / "disputed_edges.csv").open(encoding="utf-8-sig", newline="")))
    for d in disputed:
        key = (d["qid"], d["output_column"], d["source_table"], d["source_column"])
        gold.append({"qid": d["qid"], "output_column": d["output_column"],
                     "source_table": d["source_table"], "source_column": d["source_column"],
                     "decision": ADJ[key]})
        d["adjudicated_decision"] = ADJ[key]

    with (PKG / "gold_final.jsonl").open("w", encoding="utf-8") as fh:
        for r in sorted(gold, key=lambda x: (x["qid"], x["output_column"], x["source_table"], x["source_column"])):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    with (PKG / "disputed_edges.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["qid", "output_column", "source_table", "source_column",
                                           "votes", "adjudicated_decision"])
        w.writeheader()
        w.writerows(disputed)

    counts = {}
    for r in gold:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"gold_final.jsonl: {len(gold)} edges {counts}")
    for k, v in ADJ.items():
        print("adjudicated:", k, "->", v, "|", REASON[k])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
