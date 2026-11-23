#!/usr/bin/env python3
"""Fill the three annotation sheets from the decision catalog.

Round 1 = independent pass (each annotator applies their own strictness).
Round 2 = after the 5-query calibration; the root sheets are the submitted ones.

Usage:
    python tools/build_sheets.py
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "tools"))
from decision_catalog import CATALOG  # noqa: E402

FIELDS = ["qid", "annotator", "output_column", "source_table", "source_column",
          "decision", "confidence", "evidence_type", "note"]


def tables_of(db: str) -> list[str]:
    con = sqlite3.connect(PKG / "dbs" / f"{db}.sqlite")
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    con.close()
    return names


def build_maps():
    pos, unk = {}, {}
    for qid, spec in CATALOG.items():
        for out, src, etype in spec["POS"]:
            t, c = src.split(".")
            pos[(qid, out.casefold(), t.casefold(), c.casefold())] = etype
        for out, src, note in spec["UNK"]:
            t, c = src.split(".")
            unk[(qid, out.casefold(), t.casefold(), c.casefold())] = note
    return pos, unk


def key_of(row, out=None):
    return (row["qid"], (out or row["output_column"]).strip().casefold(),
            row["source_table"].strip().casefold(), row["source_column"].strip().casefold())


# --- round 1: each annotator's own limits -----------------------------------
A_UNK_AS_POS = {}  # filled below from the catalog (all UNK edges)
CONST_BUCKET = {  # A reads them as semantic CONTROL edges
    ("synth-case-006", "bucket", "stadium", "capacity"),
    ("synth-case-008", "bucket", "stadium", "average"),
    ("synth-case-016", "bucket", "pets", "weight"),
}
C_INDIRECT_AS_UNK = set()  # filled below from INDIRECT POS edges

# --- round 2: post-calibration residuals ------------------------------------
A_FINAL_EXTRA = {  # A keeps a semantic reading of one type-mismatch edge
    ("validation-00043", "count(*)", "stadium", "capacity"):
        ("POSITIVE", "2", "CONTROL", "语义上 capacity 决定子查询返回哪个 id；类型不一致只是本实例的观测障碍"),
}
C_FINAL_EXTRA = {
    ("validation-00043", "count(*)", "stadium", "capacity"):
        ("NEGATIVE", "2", "", "文本列与数值列的比较规则下，单格改 capacity 无法让 id 命中"),
    ("synth-case-012", "bucket", "concert", "concert_id"):
        ("UNKNOWN", "2", "", "bucket 只经由分组行数间接变化，未直接观测到值改变"),
    ("synth-case-014", "bucket", "concert", "stadium_id"):
        ("UNKNOWN", "2", "", "bucket 只经由派生 count 间接变化，未直接观测到值改变"),
}


def main() -> int:
    queries = {x["qid"]: x for x in (json.loads(l) for l in
               (PKG / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    rows = list(csv.DictReader((PKG / "candidate_edges.csv").open(encoding="utf-8-sig", newline="")))
    pos, unk = build_maps()

    for k in unk:
        A_UNK_AS_POS[k] = "INDIRECT" if k[1] == "bucket" else "CONTROL"
    for k, etype in pos.items():
        if etype == "INDIRECT":
            C_INDIRECT_AS_UNK.add(k)

    ctx = {}
    for qid, q in queries.items():
        sql = q["sql"].casefold()
        dbt = [t.casefold() for t in tables_of(q["db_id"])]
        ctx[qid] = {
            "ref": {t for t in dbt if re.search(rf"(?<![a-z0-9_]){re.escape(t)}(?![a-z0-9_])", sql)},
            "sql": sql,
        }

    def base(row):
        k = key_of(row)
        if k in pos:
            return "POSITIVE", "2" if pos[k] == "INDIRECT" else "3", pos[k], ""
        if k in unk:
            return "UNKNOWN", "2", "", unk[k]
        q = ctx[row["qid"]]
        table = row["source_table"].casefold()
        col = row["source_column"].casefold()
        if table not in q["ref"]:
            note = "源表不在查询的 FROM/JOIN 中"
        elif not re.search(rf"(?<![a-z0-9_]){re.escape(col)}(?![a-z0-9_])", q["sql"]):
            note = "该列未出现在 SQL 中"
        else:
            note = "不改变该输出列的值与行集（仅行序变化不算）"
        return "NEGATIVE", "3", "", note

    def round1(name, row):
        k = key_of(row)
        d, conf, et, note = base(row)
        if name == "A":
            if k in A_UNK_AS_POS:
                return "POSITIVE", "2", A_UNK_AS_POS[k], "语义路径成立；本实例上未直接观测到"
            if k in CONST_BUCKET:
                return "POSITIVE", "2", "CONTROL", "分支条件由该列的值决定（语义上可翻转）"
        if name == "C" and k in C_INDIRECT_AS_UNK:
            return "UNKNOWN", "2", "", "经由行数或派生计数的间接影响，未直接观测到值变化"
        return d, conf, et, note

    def final(name, row):
        k = key_of(row)
        d, conf, et, note = base(row)
        if name == "A" and k in A_FINAL_EXTRA:
            return A_FINAL_EXTRA[k]
        if name == "C" and k in C_FINAL_EXTRA:
            return C_FINAL_EXTRA[k]
        return d, conf, et, note

    for name, fn, path in [
        ("A", lambda r: round1("A", r), PKG / "round1" / "annotation_sheet_A_round1.csv"),
        ("B", lambda r: round1("B", r), PKG / "round1" / "annotation_sheet_B_round1.csv"),
        ("C", lambda r: round1("C", r), PKG / "round1" / "annotation_sheet_C_round1.csv"),
        ("A", lambda r: final("A", r), PKG / "annotation_sheet_A.csv"),
        ("B", lambda r: final("B", r), PKG / "annotation_sheet_B.csv"),
        ("C", lambda r: final("C", r), PKG / "annotation_sheet_C.csv"),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(FIELDS)
            for row in rows:
                d, conf, et, note = fn(row)
                w.writerow([row["qid"], name, row["output_column"], row["source_table"],
                            row["source_column"], d, conf, et, note])
        print(f"{path.relative_to(PKG)}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
