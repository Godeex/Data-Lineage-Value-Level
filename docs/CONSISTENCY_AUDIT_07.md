# Consistency Audit 07

**Date:** 2026-11-23  
**Files:** `paper/main.tex`, `paper/supplementary.tex`

## 1. Algorithm 1 ↔ `Complete(c,o)`

| Check | Status | Evidence |
|---|---|---|
| Three perturbation families included | ✅ | Algorithm 1 loops over `CellValue`, `ValueToNull`, `NullToValue` |
| Applicable rows match NULL/non-NULL scope | ✅ | `R^f_c` is family-specific; `ValueToNull` uses non-null rows, `NullToValue` uses null rows |
| Candidate enumeration complete | ✅ | `Complete(c,o)` requires all declared candidate values; row-budget truncation sets it false |
| Timeout / query error / guard prevent Negative | ✅ | `Complete(c,o)` requires no timeout, query error, or guard; `Negative` requires `q_{c,o}=true` |
| Pair-level state | ✅ | Output is `{q_{c,o}}`, not a global `q` |
| Query-level guards mapped conservatively | ✅ | Text: “Guards are query-level … every unwitnessed pair in that query is Unknown” |

## 2. Positive / Unknown / Negative priority

✅ Explicit priority sentence in Section 5.5:

> State priority is witness first: a witnessed pair is Positive even if the query also triggers a guard or exhausts its budget; otherwise an incomplete search or guard yields Unknown, and Negative requires a complete search with no witness.

This guarantees observed witnesses are not downgraded by a query-level guard.

## 3. Abstract claim

✅ Current sentence:

> On our gold sets, literal probing recovers every true-positive edge that the evaluated cell-perturbation policy recovers.

No longer implies coverage of all theoretical cell perturbations or all true dependencies.

## 4. Metric denominators

| Metric | Denominator | Status |
|---|---|---|
| Theoretical coverage / FN | `L_inst` | ✅ defined in Section 2 |
| 170-query reference coverage | `L_ref` | ✅ stated in Section 5.1 |
| 30-query human evaluation | `L_gold` | ✅ stated in Section 5.1 |
| 42-template confirmation | `L_gold` | ✅ stated in Section 5.3 |
| Negative | declared finite search space | ✅ stated in Section 5.5 |

Section 5.1 contains the unified sentence:

> Unless stated otherwise, reference coverage uses `L_ref`, accuracy on annotated subsets uses `L_gold`, and `L_inst` is not directly enumerable in our experiments.

## 5. Negative precision wording

✅ Current text separates the 184 confirmed negatives from the 6 human-unknown Negative outputs, and states:

> This does not establish absence outside the declared finite search space.

## 6. Discovery vs confirmation independence

✅ Confirmation is consistently called `post-freeze confirmation`.  
✅ It is explicitly `not an independent evolution test`.  
✅ No sentence calls the 42-template set an independent held-out test.

## 7. Machine reference naming

✅ First use:

> high-budget cell-perturbation reference … hereafter the machine reference

✅ Explicitly exhaustive over the declared policy, not all same-type replacements.  
✅ Human gold is the independent evaluation target.

## 8. Component terminology

✅ Section 5.3 distinguishes:

- Cell-only: execution cell probe
- Literal: execution literal probe
- Static+Literal: static lineage ∪ literal execution

✅ Table 15/16 narrative matches: literal covers cell-only execution TPs; static-only edges remain separate.

## 9. Novelty positioning

✅ Contribution 2 is now titled **Mechanism-driven repair** and states that the contribution is the mechanism-to-candidate mapping, not a new perturbation operator.  
✅ Related Work adds: the contribution is not execution itself, but the explicit evidence state and query-derived candidate space that make execution limits measurable and repairable.  
✅ Static/execution complementarity and Unknown semantics are stated as separate parts of the contribution rather than hidden inside a probe-operator claim.

## 10. External validity map

✅ Supplement contains an **Evidence map** that states, for each workload, what it supports and what it does not support:

- 30-query gold: blind-spot analysis and method design; not confirmatory or independent.
- 42-template confirmation: post-freeze confirmation; not evolution-independent or external benchmark.
- 170-query silver: agreement/coverage/cost; not independent gold accuracy or universal recall.
- 30 dbt/Jinja cases: heterogeneous pipeline case study; not full dbt runtime or production.
- 6 TPC-H controls: real-value scale-oriented control; not production benchmark or general accuracy.

✅ Section 5.1 points to this evidence map.

## 11. Contribution focus

✅ Evolution is retained as one sentence in the Abstract, one short Introduction paragraph, one Related Work paragraph, Section 5.7, and one Discussion paragraph.  
✅ It is explicitly labeled an **evaluation lesson**, not a third method contribution.  
✅ Related Work no longer repeats the full 21.7-point pilot/strict protocol before Section 5.7.

## 12. Final layout

- `main.pdf`: 13 pages — body 12, references start on page 13
- `supplementary.pdf`: 5 pages
- Overfull hbox: **0** in both
- Abstract: **233 words**
- No visible `Fixed` naming mismatch
- `pytest`: **29 passed, 1 skipped**

## Remaining risk

No new P0 found. The remaining weaknesses are external validity (Spider, simulated dbt/Jinja, six-query TPC-H control) and the modest independent innovation of literal candidate generation; both are now stated within the paper's scope rather than hidden.
