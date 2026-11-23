# Observability-Aware Value-Level Data Lineage

Artifact for the PVLDB 2027 submission:

> **When Execution Evidence Is Incomplete: Measuring and Repairing Observability in Value-Level Data Lineage**

Xu Gao, Sai Wu, Xiu Tang, Chang Yao, and Gang Chen — Zhejiang University

This repository contains the code, annotations, result files, and supplementary material for the study. Experimental outputs under `results/` let the reported numbers be traced without rerunning every job.

---

## What this artifact contains

- **Execution perturbation oracle** for `CELL_VALUE`, `VALUE_TO_NULL`, and `NULL_TO_VALUE`.
- **Literal-aware probing**: SQL literals, boundary values, deterministic candidate ordering, and type normalization.
- **Static + execution union**: sqlglot static lineage combined with execution-witnessed edges.
- **Operational three-state oracle**: `POSITIVE`, `UNKNOWN`, `NEGATIVE`, including pair-level completeness and query-level incompleteness guards.
- **Evaluation workloads**: 30-query discovery gold, 42-template post-freeze confirmation, 170-query silver set, 30 dbt/Jinja cases, and a TPC-H real-value control at 6k/60k/600k `lineitem` rows.
- **External comparisons**: LineageX and ProvSQL where-provenance.
- **Supplementary material**: `supplement/supplementary.tex`, its compiled PDF, and the two supplementary figures.

## Key results

- The high-budget cell-perturbation reference reaches precision `1.000` but recall `0.874` on the 30-query human gold; 10 of its 11 missed positive edges are predicate/control edges.
- Static+Literal improves macro F1 from `0.704` (Static+Cell) to `0.819` on the 42-template confirmation set (`+0.115`, 95% CI `[0.059, 0.183]`, `p < 0.001`). Literal alone is not significant (`+0.019`, `p = 0.653`).
- On 42 confirmation templates (492 edges), the operational oracle returns `POSITIVE` for `137/145` confirmed positives and `NEGATIVE` for `184/313` confirmed negatives, with **0 inversion errors**. Eight positives and 129 negatives remain `UNKNOWN` under the conservative guards.
- On TPC-H SF0.1 (`600,572` `lineitem` rows, `150,000` `orders`), cell-only probing recovers `2/8` hand-specified control edges and literal probing recovers `7/8`; the pattern is unchanged from 6k and 60k rows.
- On the same TPC-H control, ProvSQL where-provenance recovers `6/7` projection DATA edges but `0/8` control edges; aggregate where-provenance is unsupported.

---

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,figures]"
pytest -q
```

`pytest` should report `29 passed, 1 skipped`.

The default Python package is `agentdb` under `src/agentdb`.

---

## Data

### Spider databases

The artifact does **not** redistribute the Spider SQLite databases. Download Spider from its official distribution and place the SQLite files in a directory such as `data/spider/db`:

```bash
export AGENTDB_DB_DIR=/absolute/path/to/spider/db
```

Scripts that expose a `--db-dir` option also accept that path explicitly. The scripts that do not have a CLI option read `AGENTDB_DB_DIR`, falling back to the original author path `/data/gx/spider/db` for compatibility.

### TPC-H control data

The small SF0.001 control database is included:

```text
data/tpch_control.sqlite
```

The SF0.1 scale database is intentionally not committed (about 107 MB). Regenerate it with DuckDB:

```bash
python scripts/generate_tpch_sf01.py
# writes data/tpch_sf01.sqlite with 600,572 lineitem rows
```

The generator requires DuckDB with the `tpch` and `sqlite` extensions.

### Human annotations and frozen predictions

Included under:

```text
annotations/discovery/                           # 30-query discovery sheets, labels, gold
annotations/confirmation/                        # 42-template package, sheets, gold, sealed predictions
annotations/archives/                            # original packaged ZIPs
results/confirmation_gold_final.jsonl            # 42-template gold
results/confirmation_queries.jsonl
results/confirmation_agreement.json
```

Canonical annotation inputs live under `annotations/`; `results/` retains the frozen copies used by the evaluation scripts. The 42-template set is a **post-freeze confirmation** for Literal and Static+Cell. It overlaps the policy pool and is **not** an independent evolution test.

---

## Reproducing the main evaluation

From the repository root:

```bash
export AGENTDB_DB_DIR=/absolute/path/to/spider/db

python scripts/build_query_sets.py --db-dir "$AGENTDB_DB_DIR"
python scripts/run_p1_coverage.py --db-dir "$AGENTDB_DB_DIR"
python scripts/evaluate_gold.py --db-dir "$AGENTDB_DB_DIR"
python scripts/heldout_gold.py --db-dir "$AGENTDB_DB_DIR"
python scripts/evaluate_silver.py --db-dir "$AGENTDB_DB_DIR"
python scripts/evaluate_nongold.py
python scripts/literal_ablation.py
python scripts/analyze_components.py
python scripts/confidence_intervals.py
python scripts/run_p3_dbt_ext.py
python scripts/compute_stats.py
python scripts/gold_stats.py
python scripts/classify_gold_edges.py
python scripts/analyze_recovery_types.py
```

The scripts write JSON/JSONL under `results/`.

### Three-state oracle

Discovery gold:

```bash
python scripts/tristate_oracle.py \
  --db-dir "$AGENTDB_DB_DIR" \
  --out results/tristate_oracle.json
```

42-template confirmation gold:

```bash
python scripts/tristate_oracle.py \
  --gold results/confirmation_gold_final.jsonl \
  --queries results/confirmation_queries.jsonl \
  --db-dir annotations/confirmation/package/dbs \
  --out results/tristate_confirmation.json
```

The oracle uses a 30-row snapshot per query, all cell families, SQL literals, and boundary values. `NEGATIVE` is relative to the declared finite search space; a query-level guard conservatively marks all unwitnessed pairs of that query `UNKNOWN`.

### TPC-H scale and external controls

```bash
python scripts/generate_tpch_sf01.py
python scripts/tpch_scale.py
python scripts/tpch_external.py
```

`tpch_external.py` reads the included `results/provsql_tpch.json`. To regenerate the ProvSQL result from scratch, a PostgreSQL instance with ProvSQL is required; see `scripts/provsql_tpch.py` for the expected DSN and table setup. The artifact does not bundle PostgreSQL or ProvSQL.

### LineageX

`scripts/run_lineagex.py` loads LineageX from `LINEAGEX_PATH` (default `/tmp/lxenv`). A working LineageX environment is not bundled.

---

## Supplementary material

The artifact includes the supplementary material, but not the main manuscript. It can be rebuilt with a TeX distribution containing `acmart` and `libertine`:

```bash
cd supplement
pdflatex supplementary
pdflatex supplementary
```

Compiled copy:

```text
supplement/supplementary.pdf
```

`supplement/supplementary.tex` uses the two figure PDFs in `supplement/figures/`; all data needed for the supplementary tables is under `results/`.

---

## Repository layout

```text
src/agentdb/                 core library: SQLite oracle, static lineage, metrics, policy
scripts/                     experiment drivers and artifact regeneration
tests/                       unit tests
data/                        query sets, fixtures, dbt seeds, TPC-H control DB
annotations/discovery/        discovery sheets, labels, gold
annotations/confirmation/     confirmation package, results, sealed predictions
annotations/archives/         original packaged ZIPs
results/                     frozen predictions and summary results
supplement/                  supplementary source, compiled PDF, and supplementary figures
docs/                        selected experiment and audit notes
```

## Important scope notes

- The TPC-H control has **six queries and eight hand-specified control edges**. It is a scale-oriented controlled validation, not a production benchmark.
- The 30-query gold is a **discovery** set; the 42-template confirmation is a **post-freeze confirmation** for Literal/Static+Cell, not an independent evolution test.
- The 170-query silver set measures agreement with a calibrated reference, not independent gold accuracy.
- dbt/Jinja cases are simulated with Jinja2, not a full dbt runtime.
- The main workload uses SQLite affinity. Dynamic SQL, black-box UDFs, and stored procedures are outside the current scope.

## Citation

If you use this artifact, please cite the paper:

```bibtex
@inproceedings{gao2027executionlineage,
  author    = {Xu Gao and Sai Wu and Xiu Tang and Chang Yao and Gang Chen},
  title     = {When Execution Evidence Is Incomplete: Measuring and Repairing Observability in Value-Level Data Lineage},
  booktitle = {Proceedings of the VLDB Endowment},
  year      = {2027}
}
```

## License

No license has been selected for this artifact yet. Add a `LICENSE` file before making the repository public.
