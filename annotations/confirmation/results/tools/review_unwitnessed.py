"""Review table: candidate edges without a witness, with structural flags."""
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "tools"))
from decision_catalog import CATALOG  # noqa: E402


def tables_of(db):
    con = sqlite3.connect(PKG / "dbs" / f"{db}.sqlite")
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    con.close()
    return names


queries = {x["qid"]: x for x in (json.loads(l) for l in
           (PKG / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
ev = json.loads((PKG / "tools" / "evidence.json").read_text(encoding="utf-8"))
rows = list(csv.DictReader((PKG / "candidate_edges.csv").open(encoding="utf-8-sig", newline="")))

witnessed = set()
for qid, info in ev.items():
    for e in info["edges"].values():
        witnessed.add((qid, e["output_column"].casefold(), e["source_table"].casefold(),
                       e["source_column"].casefold()))

cat = {}
for qid, spec in CATALOG.items():
    for out, src, et in spec["POS"]:
        t, c = src.split(".")
        cat[(qid, out.casefold(), t.casefold(), c.casefold())] = "POS"
    for out, src, _ in spec["UNK"]:
        t, c = src.split(".")
        cat[(qid, out.casefold(), t.casefold(), c.casefold())] = "UNK"

for row in rows:
    key = (row["qid"], row["output_column"].strip().casefold(),
           row["source_table"].strip().casefold(), row["source_column"].strip().casefold())
    if key in witnessed:
        continue
    q = queries[row["qid"]]
    sql = q["sql"].casefold()
    dbt = [t.casefold() for t in tables_of(q["db_id"])]
    ref_tables = {t for t in dbt if re.search(rf"(?<![a-z0-9_]){re.escape(t)}(?![a-z0-9_])", sql)}
    in_sql = re.search(rf"(?<![a-z0-9_]){re.escape(row['source_column'].casefold())}(?![a-z0-9_])", sql)
    print("\t".join([
        row["qid"], row["output_column"], row["source_table"] + "." + row["source_column"],
        "catalog=" + cat.get(key, "-"),
        "table_ref=" + ("Y" if row["source_table"].casefold() in ref_tables else "N"),
        "col_in_sql=" + ("Y" if in_sql else "N"),
    ]))
