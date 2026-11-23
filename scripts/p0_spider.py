"""P0 pilot on real Spider databases: static vs value-level oracle agreement.

This is not an accuracy benchmark (Spider has no lineage gold labels). It
measures (a) how much syntactic lineage the oracle can observe on real DBs,
(b) where static and value-level graphs disagree, and (c) oracle cost/failures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentdb import data as data_mod
from agentdb.lineage import extract_static_lineage
from agentdb.metrics import prf
from agentdb.oracle import oracle_edges
import signal

from agentdb.spider import load_queries, load_sqlite_tables


class QueryTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise QueryTimeout("query exceeded per-item budget")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default="/data/gx/spider/spider/validation-00000-of-00001.parquet")
    parser.add_argument("--db-dir", default="/data/gx/spider/db")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--out", default="results/p0_spider.jsonl")
    args = parser.parse_args()

    queries = load_queries(args.parquet, limit=args.limit, offset=args.offset)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    failures = []
    for idx, q in enumerate(queries):
        db_path = Path(args.db_dir) / f"{q['db_id']}.sqlite"
        if not db_path.exists():
            failures.append({"idx": idx, "db_id": q["db_id"], "error": "db not found"})
            continue
        try:
            tables = load_sqlite_tables(db_path, max_rows=50)
            schema = {name: dict(spec["columns"]) for name, spec in tables.items()}
            static = extract_static_lineage(q["sql"], schema, dialect="sqlite")
            script = {"id": f"spider-{idx:04d}", "sql": q["sql"], "dialect": "sqlite", "tables": tables}
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(15)
            try:
                observed, meta = oracle_edges(script, max_witness_rows=3)
            finally:
                signal.alarm(0)
        except Exception as exc:  # noqa: BLE001 - record per-query failure
            failures.append({"idx": idx, "db_id": q["db_id"], "sql": q["sql"],
                             "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not static and not observed:
            continue
        def norm(edges):
            return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}

        static_n = norm(static)
        observed_n = norm(observed)
        inter = static_n & observed_n
        row = {
            "idx": idx,
            "db_id": q["db_id"],
            "sql": q["sql"],
            "question": q["question"],
            "n_static": len(static_n),
            "n_oracle": len(observed_n),
            "n_intersection": len(inter),
            "static_only": sorted(static_n - observed_n),
            "oracle_only": sorted(observed_n - static_n),
            "coverage_of_static": len(inter) / len(static_n) if static_n else None,
            "oracle_precision_vs_static": prf(observed_n, static_n)["precision"],
            "oracle_meta": meta,
        }
        rows.append(row)

    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    coverage_values = [r["coverage_of_static"] for r in rows if r["coverage_of_static"] is not None]
    summary = {
        "n_queries_requested": len(queries),
        "n_queries_with_edges": len(rows),
        "n_failed": len(failures),
        "mean_static_edges": sum(r["n_static"] for r in rows) / len(rows) if rows else 0.0,
        "mean_oracle_edges": sum(r["n_oracle"] for r in rows) / len(rows) if rows else 0.0,
        "mean_coverage_of_static": sum(coverage_values) / len(coverage_values) if coverage_values else None,
        "n_queries_static_only_nonempty": sum(1 for r in rows if r["static_only"]),
        "n_queries_oracle_only_nonempty": sum(1 for r in rows if r["oracle_only"]),
        "failures": failures[:20],
        "out": str(out_path),
    }
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
