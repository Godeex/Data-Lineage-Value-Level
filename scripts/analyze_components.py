"""Recompute static / cell-only / literal / union components for discovery and confirmation."""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

ROOT = Path(__file__).resolve().parents[1]
DBDIR = Path(os.environ.get("AGENTDB_DB_DIR", "/data/gx/spider/db"))


def norm(edges, names):
    out = set()
    for o, t, c in edges:
        o = str(o).casefold().strip()
        m = re.fullmatch(r"_col_(\d+)", o)
        if m and int(m.group(1)) < len(names):
            o = str(names[int(m.group(1))]).casefold().strip()
        out.add((o, str(t).casefold().strip(), str(c).casefold().strip()))
    return out


def output_names(db_path: Path, sql: str):
    import sqlite3
    c = sqlite3.connect(str(db_path))
    try:
        cur = c.execute(sql)
        return [d[0] for d in (cur.description or [])]
    except Exception:
        return []
    finally:
        c.close()


def load_gold(path):
    gold = defaultdict(lambda: {"POSITIVE": set(), "NEGATIVE": set(), "UNKNOWN": set()})
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        edges = r.get("edges")
        if edges is None:
            edges = [r]
            qid = r["qid"]
        else:
            qid = r["qid"]
        for e in edges:
            d = str(e.get("decision", "UNKNOWN")).upper()
            if d not in gold[qid]:
                d = "UNKNOWN"
            gold[qid][d].add((e["output_column"].casefold(), e["source_table"].casefold(), e["source_column"].casefold()))
    return gold


def evaluate(name, qids, gold, p1, main):
    sets = {"static": set(), "cell": set(), "literal": set()}
    fps = {"static": set(), "cell": set(), "literal": set()}
    for qid in qids:
        row = main[qid]
        db = DBDIR / f"{row['db_id']}.sqlite"
        names = output_names(db, row["sql"])
        static = norm(p1[qid]["static_edges"], names)
        tables = load_sqlite_tables(db, max_rows=30)
        cell = norm(limited_edges({"sql": row["sql"], "tables": tables}, ["CELL_VALUE"], 3)["edges"], names)
        lit = norm(literal_edges({"sql": row["sql"], "tables": tables}, budget=3)["edges"], names)
        for k, v in (("static", static), ("cell", cell), ("literal", lit)):
            sets[k] |= {(qid, *e) for e in v}
            fps[k] |= {(qid, *e) for e in (v & gold[qid]["NEGATIVE"])}
    positives = {(qid, *e) for qid, g in gold.items() if qid in qids for e in g["POSITIVE"]}
    result = {"n": len(qids), "positives": len(positives)}
    for k, v in sets.items():
        tp = len(v & positives); fp = len(fps[k])
        result[k] = {"tp": tp, "fp": fp, "recall": tp / len(positives), "precision": tp / (tp + fp) if tp + fp else 1.0}
    combos = {
        "cell_literal": sets["cell"] | sets["literal"],
        "static_literal": sets["static"] | sets["literal"],
        "static_cell": sets["static"] | sets["cell"],
        "static_cell_literal": sets["static"] | sets["cell"] | sets["literal"],
    }
    for k, v in combos.items():
        tp = len(v & positives); fp = len(v & {(qid, *e) for qid, g in gold.items() if qid in qids for e in g["NEGATIVE"]})
        result[k] = {"tp": tp, "fp": fp, "recall": tp / len(positives), "precision": tp / (tp + fp) if tp + fp else 1.0}
    return result


def main() -> int:
    main_rows = {json.loads(l)["qid"]: json.loads(l) for l in (ROOT / "data/spider_main.jsonl").read_text().splitlines()}
    p1 = {json.loads(l)["qid"]: json.loads(l) for l in (ROOT / "results/p1_coverage.jsonl").read_text().splitlines()}
    disc_gold = load_gold(ROOT / "annotations/discovery/results/gold_edges.jsonl")
    disc_qids = sorted(disc_gold)
    conf_gold = load_gold(ROOT / "results/confirmation_gold_final.jsonl")
    conf_qids = sorted(conf_gold)
    out = {"discovery": evaluate("discovery", disc_qids, disc_gold, p1, main_rows),
           "confirmation": evaluate("confirmation", conf_qids, conf_gold, p1, main_rows)}
    (ROOT / "results/component_analysis.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
