# Annotation Data

This directory contains all human-annotation material in one place.

## Layout

```text
annotations/
  discovery/
    package/       # 30-query discovery annotation sheets and sample
    results/       # discovery labels, arbitration, kappa, gold_edges.jsonl
  confirmation/
    package/       # 42-template confirmation package (sheets, queries, sealed predictions, DBs)
    results/       # returned confirmation sheets, agreement, gold_final, notes
  archives/        # original packaged ZIPs, renamed for provenance
```

### Discovery set

- `discovery/package/sample_30.jsonl`: the 30 sampled queries.
- `discovery/package/annotation_sheet.csv`: blank annotation sheet.
- `discovery/results/gold_edges.jsonl`: final discovery gold, used by `scripts/evaluate_gold.py`, `scripts/tristate_oracle.py`, and related scripts.
- `discovery/results/kappa_report.json`: pairwise agreement.
- `discovery/results/annotation_{A,B,C}.csv`: individual annotator labels.
- `discovery/results/arbitration.md`: adjudication notes.

### Confirmation set

- `confirmation/package/`: the frozen package distributed to annotators.
- `confirmation/results/gold_final.jsonl`: final 42-template gold.
- `confirmation/results/confirmation_results.json`: scored confirmation results.
- `confirmation/results/agreement_report.json`: annotation agreement.
- `confirmation/results/sealed/predictions.jsonl`: frozen machine predictions used for scoring.

The 42-template set is a **post-freeze confirmation** for Literal and Static+Cell. It overlaps the policy pool and is **not** an independent evolution test.

### Archives

`archives/` preserves the original ZIPs with clearer names. The unpacked directories above are the canonical copies used by the code and paper.

## Paths used by scripts

The main script defaults now point to:

```text
annotations/discovery/results/gold_edges.jsonl
annotations/discovery/package/sample_30.jsonl
annotations/confirmation/results/sealed/predictions.jsonl
annotations/confirmation/package/dbs/
```

If you move these directories, update the corresponding defaults in `scripts/` or pass the path explicitly where supported.
