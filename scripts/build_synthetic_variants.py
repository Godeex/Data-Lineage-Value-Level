"""Add controlled CTE and CASE variants to the Spider main set.

The natural Spider validation split has few executable CTE/CASE queries that
return rows, so we derive controlled variants from existing non-empty queries.
These are labeled `source=synthetic_variant` and are not claimed as natural
Spider distribution.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from agentdb.query_sets import classify_sql, write_jsonl


def _numeric_output_column(db_path: Path, sql: str) -> str | None:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchall()[:5]
    finally:
        conn.close()
    for idx, col in enumerate(cols):
        vals = [row[idx] for row in rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            return col
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", default="data/spider_main.jsonl")
    parser.add_argument("--db-dir", default="/data/gx/spider/db")
    parser.add_argument("--n-cte", type=int, default=20)
    parser.add_argument("--n-case", type=int, default=20)
    args = parser.parse_args()

    main_rows = [json.loads(line) for line in Path(args.main).read_text(encoding="utf-8").splitlines()]
    base_rows = [r for r in main_rows if r["category"] in {"projection", "aggregate"}]
    db_dir = Path(args.db_dir)
    variants = []
    cte_count = case_count = 0
    for row in base_rows:
        db_path = db_dir / f"{row['db_id']}.sqlite"
        sql = row["sql"].rstrip().rstrip(";")
        if cte_count < args.n_cte:
            sql_cte = f"WITH base AS ({sql}) SELECT * FROM base"
            variants.append({
                "qid": f"synth-cte-{cte_count:03d}", "db_id": row["db_id"],
                "sql": sql_cte, "question": "controlled CTE variant",
                "category": "cte", "features": classify_sql(sql_cte), "n_rows": row["n_rows"],
                "source": "synthetic_variant", "base_qid": row["qid"],
            })
            cte_count += 1
        if case_count < args.n_case:
            col = _numeric_output_column(db_path, sql)
            if col:
                quoted = '"' + col.replace('"', '""') + '"'
                sql_case = (
                    f'SELECT *, CASE WHEN {quoted} > 0 THEN \'pos\' ELSE \'nonpos\' END AS bucket '
                    f"FROM ({sql}) AS base"
                )
                variants.append({
                    "qid": f"synth-case-{case_count:03d}", "db_id": row["db_id"],
                    "sql": sql_case, "question": "controlled CASE variant",
                    "category": "case", "features": classify_sql(sql_case), "n_rows": row["n_rows"],
                    "source": "synthetic_variant", "base_qid": row["qid"],
                })
                case_count += 1
        if cte_count >= args.n_cte and case_count >= args.n_case:
            break
    write_jsonl(args.main, main_rows + variants)
    summary = {"n_cte_added": cte_count, "n_case_added": case_count,
               "n_total": len(main_rows) + len(variants)}
    Path("data/variants_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
