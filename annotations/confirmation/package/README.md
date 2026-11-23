# AgentDB confirmation annotation package

This package contains everything needed to run a **blind human-gold confirmation** of
literal-aware probing on 42 SQL templates that were not used to design the method.

## What is inside

- `queries.jsonl` — 42 queries with database id, category, SQL, question, output columns, tables.
- `candidate_edges.csv` — 492 neutral candidate edges enumerated from SQL-referenced columns.
- `annotation_sheet_A.csv`, `annotation_sheet_B.csv`, `annotation_sheet_C.csv` — one blank sheet per annotator.
- `dbs/` — 10 SQLite databases (read-only copies).
- `schemas/` — table/column JSON for each database.
- `ANNOTATION.md` — definitions, decisions, workflow, quality checks.
- `inspect_db.py` — read-only schema/query helper.
- `check_sheet.py` — validates a filled sheet.
- `compute_agreement.py` — pairwise kappa, majority gold, disputed edges.
- `score_confirmation.py` — frozen fixed/literal/union predictions vs adjudicated gold, with paired bootstrap.
- `freeze_config.json` — frozen probe parameters and source hashes.
- `sealed/` — frozen machine predictions. **Do not open before labels are frozen.**

## Quick start

```bash
# 1. Inspect one database
python inspect_db.py --db dbs/concert_singer.sqlite --schema

# 2. Annotators fill their own CSV, then validate
python check_sheet.py --sheet annotation_sheet_A.csv

# 3. Coordinator: agreement and majority gold
python compute_agreement.py \
  --a annotation_sheet_A.csv \
  --b annotation_sheet_B.csv \
  --c annotation_sheet_C.csv

# 4. Adjudicate disputed_edges.csv, write gold_final.jsonl, then score
python score_confirmation.py --gold gold_final.jsonl
```

## Blinding

`candidate_edges.csv` contains only columns that appear in the SQL or are reachable through a
`SELECT *`; it does **not** contain machine-reference, static-parser, or literal-probing predictions.
The machine predictions are in `sealed/predictions.jsonl`; do not read that file until all three
sheets are complete.

## Scope

These 42 templates come from the 78-query non-gold strict pool. They are independent of literal
candidate design, but some were used in evolution-policy training/validation. Literal probing and the
fixed hybrid are deterministic and were not trained on any query; therefore this package confirms
literal vs fixed, not evolution.

## Reproducibility

`freeze_config.json` records the budget, candidate order, families, and SHA-256 of the relevant source
files. `sealed/predictions.sha256` pins the sealed prediction file.
