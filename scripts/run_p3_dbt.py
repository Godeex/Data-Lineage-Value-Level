"""P3: dbt-style Jinja macro scenario. Raw templates vs expanded SQL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agentdb.data import schema_for
from agentdb.lineage import extract_static_lineage
from agentdb.sqlite_oracle import limited_edges, reference_edges

MODELS = ["stg_orders", "stg_customers", "revenue_by_customer", "order_flags"]
VARIANTS = [{"include_refunds": False}, {"include_refunds": True}]


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def prf(pred, gold):
    pred, gold = set(pred), set(gold)
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def build_env(root: Path, tables: dict):
    env = Environment(
        loader=FileSystemLoader([str(root / "models"), str(root / "macros")]),
        autoescape=False,
        keep_trailing_newline=False,
    )
    registry = {name: (root / "models" / f"{name}.sql").read_text(encoding="utf-8") for name in MODELS}
    stack: list[str] = []

    class Macros:
        @staticmethod
        def price_bucket(expr: str, threshold) -> str:
            return f"CASE WHEN {expr} > {threshold} THEN 'high' ELSE 'low' END"

    env.globals["m"] = Macros()

    def ref(name: str) -> str:
        if name in stack:
            raise ValueError(f"cyclic ref: {name}")
        stack.append(name)
        try:
            return "(" + render(registry[name]) + ")"
        finally:
            stack.pop()

    def render(raw: str) -> str:
        return env.from_string(raw).render(ref=ref, var=lambda k, default=None: VARS.get(k, default))

    global VARS
    return env, registry, render


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/dbt_jinja")
    parser.add_argument("--seed", default="data/dbt_jinja/seed.json")
    parser.add_argument("--out", default="results/p3_dbt.json")
    args = parser.parse_args()
    root = Path(args.root)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    tables = seed["tables"]
    schema = {name: dict(spec["columns"]) for name, spec in tables.items()}

    records = []
    global VARS
    for variant in VARIANTS:
        VARS = variant
        env, registry, render = build_env(root, tables)
        for model in MODELS:
            raw = registry[model]
            expanded = render(raw)
            rec = {"model": model, "variant": variant, "expanded_sql": expanded}
            # Raw-template static lineage
            try:
                raw_edges = norm(extract_static_lineage(raw, schema, dialect="sqlite"))
                rec["raw_static_status"] = "parsed"
                rec["raw_static_edges"] = sorted(raw_edges)
            except Exception as exc:  # noqa: BLE001
                rec["raw_static_status"] = f"error: {type(exc).__name__}: {exc}"
                rec["raw_static_edges"] = []
            # Expanded static lineage
            try:
                expanded_edges = norm(extract_static_lineage(expanded, schema, dialect="sqlite"))
                rec["expanded_static_status"] = "parsed"
                rec["expanded_static_edges"] = sorted(expanded_edges)
            except Exception as exc:  # noqa: BLE001
                rec["expanded_static_status"] = f"error: {type(exc).__name__}: {exc}"
                expanded_edges = set()
            # Reference and limited oracle
            try:
                ref = reference_edges({"sql": expanded, "tables": tables})
                ref_edges = norm(ref["edges"])
                base = limited_edges({"sql": expanded, "tables": tables}, ["CELL_VALUE"], 3)
                allcell = limited_edges(
                    {"sql": expanded, "tables": tables},
                    ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], 10,
                )
                rec.update({
                    "n_ref": len(ref_edges),
                    "ref_edges": sorted(ref_edges),
                    "expanded_static_precision": prf(expanded_edges, ref_edges)[0],
                    "expanded_static_recall": prf(expanded_edges, ref_edges)[1],
                    "expanded_static_f1": prf(expanded_edges, ref_edges)[2],
                    "base_coverage": (len(norm(base["edges"]) & ref_edges) / len(ref_edges)) if ref_edges else None,
                    "allcell_coverage": (len(norm(allcell["edges"]) & ref_edges) / len(ref_edges)) if ref_edges else None,
                    "base_edges": sorted(norm(base["edges"])),
                    "allcell_edges": sorted(norm(allcell["edges"])),
                })
            except Exception as exc:  # noqa: BLE001
                rec["oracle_status"] = f"error: {type(exc).__name__}: {exc}"
            records.append(rec)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "n_records": len(records),
        "raw_static_parsed": sum(1 for r in records if r["raw_static_status"] == "parsed"),
        "raw_static_errors": sum(1 for r in records if r["raw_static_status"] != "parsed"),
        "expanded_static_parsed": sum(1 for r in records if r.get("expanded_static_status") == "parsed"),
        "mean_expanded_static_f1": sum(r.get("expanded_static_f1", 0.0) for r in records) / len(records),
        "mean_base_coverage": sum(r.get("base_coverage") or 0.0 for r in records) / len(records),
        "mean_allcell_coverage": sum(r.get("allcell_coverage") or 0.0 for r in records) / len(records),
    }
    Path(args.out).with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
