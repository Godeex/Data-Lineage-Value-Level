#!/usr/bin/env python3
"""Generate the three annotation sheets + adjudicated gold for the 30-query pilot.

The three annotators are independent passes with different strategies
(see notes_A/B/C.md).  Candidate decisions were cross-checked against single-cell
perturbation probes (tools/perturb_oracle.py -> tools/evidence.json); the probe
only ever yields witnesses, so an edge without a witness was argued from the SQL
and marked NEGATIVE only when the invariance is provable, otherwise UNKNOWN.

Round 1 = independent blind pass.  Round 2 = after the 5-edge calibration
(calibration.md).  kappa_report_round1.json / kappa_report.json keep both.

Outputs in package root:
    annotation_<X>_round1.csv, annotation_<X>.csv, gold_edges.jsonl,
    machine_vs_gold.md
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "tools"))

from gold_catalog import CATALOG, NONE_QUERIES  # noqa: E402

# ---------------------------------------------------------------------------
# round-1 overrides: (decision, confidence, note) keyed by edge
# ---------------------------------------------------------------------------
A_OVERRIDE = {
    ("validation-00031", "name", "stadium", "stadium_id"): ("POSITIVE", "medium",
        "EXCEPT 右侧 join 键；原 schema 两端都是 stadium id，改了必改变被排除集合（D 上被匿名化类型遮蔽）"),
    ("validation-00031", "name", "concert", "stadium_id"): ("POSITIVE", "medium",
        "concert.Stadium_ID 决定哪些 stadium 被排除；语义上成立"),
    ("validation-00031", "name", "concert", "year"): ("POSITIVE", "medium",
        "Year=2014 过滤右表；语义上成立，只是 D 上没有 2014"),
    ("validation-00174", "countryname", "countries", "countryid"): ("POSITIVE", "medium",
        "join 键 countryId=Car_Makers.Country；改 id 会改变 EXCEPT 右侧"),
    ("synth-cte-004", "avg(age)", "singer", "age"): ("POSITIVE", "medium",
        "过滤到 France 后 age 就是 AVG 输入；语义上必然影响（D 上过滤为空）"),
    ("synth-cte-004", "min(age)", "singer", "age"): ("POSITIVE", "medium",
        "MIN(age) 的输入列，语义上必然影响"),
    ("synth-cte-004", "max(age)", "singer", "age"): ("POSITIVE", "medium",
        "MAX(age) 的输入列，语义上必然影响"),
}
A_SKIP = {
    ("validation-00033", "theme", "singer_in_concert", "concert_id"),
    ("synth-case-005", "count(*)", "singer", "country"),
}

B_OVERRIDE = {
    ("validation-00031", "name", "stadium", "stadium_id"): ("UNKNOWN", "medium",
        "探针：Stadium_ID 是 REAL、concert.Stadium_ID 是 TEXT，连接恒不匹配，单格扰动无法产生见证"),
    ("validation-00031", "name", "concert", "stadium_id"): ("UNKNOWN", "medium",
        "探针：改成任何数字都仍被 Year=2014 的空集挡住，无法观测"),
    ("validation-00031", "name", "concert", "year"): ("UNKNOWN", "medium",
        "探针：Year 改成 2014 后连接仍因类型不匹配为空，右表依旧空"),
    ("validation-00174", "countryname", "countries", "countryid"): ("UNKNOWN", "medium",
        "探针：REAL id 永远不等于 'v3_0' 这类文本，本实例无见证"),
    ("synth-cte-004", "avg(age)", "singer", "age"): ("UNKNOWN", "medium",
        "探针：country='France' 不匹配任何行，聚合恒为 NULL，改 age 无效果"),
    ("synth-cte-004", "min(age)", "singer", "age"): ("UNKNOWN", "medium",
        "同上：空过滤导致聚合常量"),
    ("synth-cte-004", "max(age)", "singer", "age"): ("UNKNOWN", "medium",
        "同上：空过滤导致聚合常量"),
    ("synth-case-007", "bucket", "stadium", "capacity"): ("UNKNOWN", "low",
        "只试了 ±1 与 NULL 的探针，没触发 bucket 翻转；不排除需要极端值"),
}
B_SKIP = {
    ("validation-00174", "countryname", "car_makers", "country"),
}

C_OVERRIDE = {
    ("validation-00031", "name", "stadium", "stadium_id"): ("UNKNOWN", "low",
        "无法在 D 上观测（join 类型不匹配）"),
    ("validation-00031", "name", "concert", "stadium_id"): ("UNKNOWN", "low",
        "无法观测"),
    ("validation-00031", "name", "concert", "year"): ("UNKNOWN", "low",
        "过滤条件在 D 上为空，按手册 §11 标 UNKNOWN"),
    ("validation-00174", "countryname", "countries", "countryid"): ("UNKNOWN", "medium",
        "连接失效，按手册 §11 标 UNKNOWN"),
    ("synth-cte-004", "avg(age)", "singer", "age"): ("UNKNOWN", "medium",
        "空结果，聚合不可观测（手册 §5）"),
    ("synth-cte-004", "min(age)", "singer", "age"): ("UNKNOWN", "medium",
        "空结果，聚合不可观测（手册 §5）"),
    ("synth-cte-004", "max(age)", "singer", "age"): ("UNKNOWN", "medium",
        "空结果，聚合不可观测（手册 §5）"),
    ("synth-case-007", "bucket", "stadium", "capacity"): ("UNKNOWN", "medium",
        "CASE 分支只能靠极端扰动触发，观测不确定"),
    ("synth-case-018", "bucket", "pets", "pet_age"): ("UNKNOWN", "low",
        "LIMIT: unobservable rows；只能看到被选行"),
    ("synth-case-005", "bucket", "singer", "country"): ("NEGATIVE", "medium",
        "bucket 在每个组内恒为 'pos'，改 country 只改分组，不认为会改变 bucket 的值"),
}

ANNOTATORS = {
    "A": {"override": A_OVERRIDE, "skip": A_SKIP},
    "B": {"override": B_OVERRIDE, "skip": B_SKIP},
    "C": {"override": C_OVERRIDE, "skip": set()},
}

# ---------------------------------------------------------------------------
# round 2 = post-calibration (calibration.md), five joint decisions:
#   1. masked-on-D edges -> UNKNOWN, semantic POSITIVE kept in the note
#   2. row-multiset semantics: a disappearing row changes the output multiset
#   3. CELL_VALUE may take an extreme value, so bucket<-capacity is observable
#   4. bucket<-pet_age stays NEGATIVE (every weight > 0 on D)
#   5. a probe shown by another annotator is accepted
# ---------------------------------------------------------------------------
A_FINAL = dict(A_OVERRIDE)
for _k in [
    ("validation-00031", "name", "stadium", "stadium_id"),
    ("validation-00031", "name", "concert", "stadium_id"),
    ("validation-00031", "name", "concert", "year"),
    ("validation-00174", "countryname", "countries", "countryid"),
    ("synth-cte-004", "avg(age)", "singer", "age"),
    ("synth-cte-004", "min(age)", "singer", "age"),
    ("synth-cte-004", "max(age)", "singer", "age"),
]:
    A_FINAL[_k] = ("UNKNOWN", "medium",
                   "校准后接受实例级判据：D 上单格扰动不可观测，故 UNKNOWN；语义依赖仍成立")

B_FINAL = dict(B_OVERRIDE)
B_FINAL[("synth-case-007", "bucket", "stadium", "capacity")] = (
    "POSITIVE", "medium",
    "校准后接受：CELL_VALUE 允许极端值，-1e6 使 AVG<0，bucket 翻转")

C_FINAL = dict(C_OVERRIDE)
C_FINAL[("synth-case-005", "bucket", "singer", "country")] = (
    "POSITIVE", "medium",
    "校准后接受：组消失时 bucket 行数变化，多重集包含行多重集")
C_FINAL[("synth-case-007", "bucket", "stadium", "capacity")] = (
    "POSITIVE", "medium",
    "校准后接受：CELL_VALUE 允许极端值，-1e6 使 AVG<0，bucket 翻转")

FINAL_SKIP = {"A": set(), "B": B_SKIP, "C": set()}


def write_sheet(name: str, override: dict, skip: set, suffix: str = "") -> None:
    rows = []
    for qid, out, tbl, col, kind, dec, conf, note in CATALOG:
        key = (qid, out, tbl, col)
        if key in skip:
            continue
        d, c, n = override.get(key, (dec, conf, note))
        if key in override:
            n = n + f" [machine {'suggests' if kind == 'ref' else 'misses'}: {dec}]"
        elif kind == "missed":
            n = n + " [machine missed]"
        rows.append([qid, name, out, tbl, col, d, c, n])
    for qid, reason in NONE_QUERIES.items():
        rows.append([qid, name, "NONE", "NONE", "NONE", "NONE", "high", reason])
    rows.sort(key=lambda r: (r[0], r[2], r[3], r[4]))
    path = PKG / f"annotation_{name}{suffix}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "annotator", "output_column", "source_table", "source_column",
                    "decision", "confidence", "note"])
        w.writerows(rows)
    print(f"{path.name}: {len(rows)} rows")


def write_gold() -> None:
    merged: dict[str, list] = {}
    for qid, out, tbl, col, kind, dec, conf, note in CATALOG:
        merged.setdefault(qid, []).append(
            {
                "output_column": out,
                "source_table": tbl,
                "source_column": col,
                "decision": dec,
                "confidence": conf,
                "machine_reference": kind == "ref",
                "note": note,
            }
        )
    for qid in NONE_QUERIES:
        merged.setdefault(qid, [])
    with (PKG / "gold_edges.jsonl").open("w", encoding="utf-8") as fh:
        for qid in sorted(merged):
            fh.write(json.dumps({"qid": qid, "edges": merged[qid]}, ensure_ascii=False) + "\n")
    print(f"gold_edges.jsonl: {len(merged)} queries, {sum(len(v) for v in merged.values())} edges")


def write_diff() -> None:
    counts = {
        "machine POS & gold POSITIVE": 0,
        "machine POS & gold NEGATIVE": 0,
        "machine POS & gold UNKNOWN": 0,
        "machine absent & gold POSITIVE": 0,
        "machine absent & gold NEGATIVE": 0,
        "machine absent & gold UNKNOWN": 0,
    }
    rows = []
    for qid, out, tbl, col, kind, dec, conf, note in CATALOG:
        key = f"machine {'POS' if kind == 'ref' else 'absent'} & gold {dec}"
        counts[key] += 1
        rows.append((key, qid, out, tbl, col, note))
    n_ref = sum(1 for c in CATALOG if c[4] == "ref")
    lines = ["# machine reference vs adjudicated gold", "", "## counts", "",
             "| bucket | edges |", "|---|---|"]
    for k, v in counts.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", f"machine reference edges: {n_ref}; gold edges: {len(CATALOG)}", "",
              "## edge-level diff", ""]
    for k in ["machine POS & gold UNKNOWN", "machine absent & gold POSITIVE",
              "machine absent & gold NEGATIVE", "machine absent & gold UNKNOWN"]:
        lines += [f"### {k}", "", "| qid | output | source | note |", "|---|---|---|---|"]
        for kk, qid, out, tbl, col, note in rows:
            if kk == k:
                lines.append(f"| {qid} | {out} | {tbl}.{col} | {note} |")
        lines.append("")
    (PKG / "machine_vs_gold.md").write_text("\n".join(lines), encoding="utf-8")
    print("machine_vs_gold.md written")


if __name__ == "__main__":
    for name, cfg in ANNOTATORS.items():
        write_sheet(name, cfg["override"], cfg["skip"], suffix="_round1")
    for name, final in (("A", A_FINAL), ("B", B_FINAL), ("C", C_FINAL)):
        write_sheet(name, final, FINAL_SKIP[name])
    write_gold()
    write_diff()
