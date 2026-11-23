"""Operational three-state lineage oracle.

For each candidate edge we return one of:
  POSITIVE - an execution witness exists in the declared search space;
  NEGATIVE - the search space was exhausted and no witness exists;
  UNKNOWN  - the search was truncated, timed out, or could not run.

The declared space here is the 30-row snapshot used by the main evaluation,
all cell-value/null families, and all SQL-literal/boundary candidates.  This
is a bounded instance-level claim, not a proof of universal absence.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import literal_edges, reference_edges

POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"
UNKNOWN = "UNKNOWN"


def norm_edge(edge) -> tuple[str, str, str]:
    o, t, c = edge
    return (str(o).casefold().strip(), str(t).casefold().strip(), str(c).casefold().strip())


def output_names(db_path: Path, sql: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(sql)
        return [str(d[0]).casefold().strip() for d in (cur.description or [])]
    except Exception:
        return []
    finally:
        conn.close()


def normalize_edges(edges, names: list[str]) -> set[tuple[str, str, str]]:
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        m = re.fullmatch(r"_col_(\d+)", o)
        if m and int(m.group(1)) < len(names):
            o = names[int(m.group(1))]
        out.add((o, str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def incompleteness_guard(db_path: Path, sql: str) -> str | None:
    """Return why a no-witness result is not conclusive, or None.

    Single-cell search is incomplete for set difference (a change can cancel
    across both sides), for an empty base result (a filter column must be
    changed together with the probed column), and for grouped aggregates
    (group membership and aggregate values change jointly).
    """
    upper = sql.upper()
    if re.search(r"\b(EXCEPT|INTERSECT)\b", upper):
        return "set_difference"
    if re.search(r"[=<>]\s*\(\s*SELECT\b", upper) or re.search(r"\bIN\s*\(\s*SELECT\b", upper):
        return "subquery_candidate"
    if re.search(r"\bGROUP\s+BY\b", upper):
        return "grouped_aggregate"
    conn = sqlite3.connect(str(db_path))
    try:
        first = conn.execute(sql).fetchmany(1)
        if not first:
            return "empty_base"
        if first and all(value is None for value in first[0]):
            return "null_only_result"
    except Exception:
        return "query_error"
    finally:
        conn.close()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="annotations/discovery/results/gold_edges.jsonl")
    ap.add_argument("--queries", default="data/spider_main.jsonl")
    ap.add_argument("--db-dir", default="/data/gx/spider/db")
    ap.add_argument("--out", default="results/tristate_oracle.json")
    ap.add_argument("--max-rows", type=int, default=30)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-candidates", type=int, default=20)
    args = ap.parse_args()

    gold = {}
    for line in Path(args.gold).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if "edges" in row:
            gold.setdefault(row["qid"], []).extend(row["edges"])
        else:
            gold.setdefault(row["qid"], []).append(row)
    main_rows = {json.loads(l)["qid"]: json.loads(l)
                 for l in Path(args.queries).read_text(encoding="utf-8").splitlines()}

    per_query = []
    totals = {h: {s: 0 for s in (POSITIVE, NEGATIVE, UNKNOWN)}
              for h in ("POSITIVE", "NEGATIVE", "UNKNOWN")}
    t0 = time.perf_counter()
    for qid, edges in gold.items():
        if qid not in main_rows:
            continue
        row = main_rows[qid]
        db_path = Path(args.db_dir) / f"{row['db_id']}.sqlite"
        names = output_names(db_path, row["sql"])
        guard = incompleteness_guard(db_path, row["sql"])
        item = {
            "qid": qid,
            "db_id": row["db_id"],
            "category": row.get("category"),
            "guard": guard,
            "states": [],
            "oracle_executions": 0,
            "oracle_seconds": 0.0,
            "error": None,
        }
        try:
            tables = load_sqlite_tables(db_path, max_rows=args.max_rows)
            script = {"sql": row["sql"], "tables": tables}
            start = time.perf_counter()
            ref = reference_edges(script, timeout_s=args.timeout)
            lit = literal_edges(script, budget=None, timeout_s=args.timeout,
                                max_candidates=args.max_candidates)
            elapsed = time.perf_counter() - start
            witnessed = normalize_edges(ref["edges"] | lit["edges"], names)
            item["oracle_executions"] = ref["executions"] + lit["executions"]
            item["oracle_seconds"] = round(elapsed, 3)
            exhaustive = True
        except Exception as exc:  # timeout / unsupported SQL
            witnessed = set()
            exhaustive = False
            item["error"] = f"{type(exc).__name__}: {exc}"

        for e in edges:
            edge = norm_edge((e["output_column"], e["source_table"], e["source_column"]))
            if edge in witnessed:
                state = POSITIVE
            elif not exhaustive:
                state = UNKNOWN
            elif guard is not None:
                state = UNKNOWN
            else:
                state = NEGATIVE
            item["states"].append({
                "edge": list(edge),
                "human": e["decision"],
                "state": state,
            })
            totals[e["decision"]][state] += 1
        per_query.append(item)
        print(qid, item["error"] or f"{len(witnessed)} witnessed", item["oracle_seconds"])

    summary = {
        "n_queries": len(per_query),
        "n_oracle_errors": sum(1 for q in per_query if q["error"]),
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
        "human_by_state": totals,
        "total_executions": sum(q["oracle_executions"] for q in per_query),
        "mean_seconds": sum(q["oracle_seconds"] for q in per_query) / max(1, len(per_query)),
    }
    payload = {"summary": summary, "per_query": per_query}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
