"""Expanded dbt/Jinja evaluation (9 models x 3 configs)."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agentdb.data import schema_for
from agentdb.lineage import extract_static_lineage
from agentdb.sqlite_oracle import literal_edges, limited_edges, reference_edges

MODELS = ["stg_orders", "stg_customers", "revenue_by_customer", "order_flags",
          "revenue_by_country", "customer_segments", "refund_rate", "top_orders",
          "taxed_revenue", "order_summary"]
CONFIGS = [
    {"include_refunds": False, "region": "US", "include_tax": False},
    {"include_refunds": True, "region": "UK", "include_tax": True},
    {"include_refunds": False, "region": "DE", "include_tax": True},
]


def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a, b, c in edges}


def metrics(pred, silver):
    tp = len(pred & silver); outside = len(pred - silver); missing = len(silver - pred)
    p = tp / (tp + outside) if tp + outside else 0.0
    r = tp / (tp + missing) if tp + missing else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "outside": outside, "missing": missing, "precision": p, "recall": r, "f1": f}


def main() -> int:
    root = Path("data/dbt_jinja_ext")
    seed = json.loads((root / "seed.json").read_text(encoding="utf-8"))
    tables = seed["tables"]
    schema = {name: dict(spec["columns"]) for name, spec in tables.items()}
    env = Environment(loader=FileSystemLoader([str(root / "models"), str(root / "macros")]), autoescape=False)

    class Macros:
        @staticmethod
        def price_bucket(expr, threshold):
            return f"CASE WHEN {expr} > {threshold} THEN 'high' ELSE 'low' END"

        @staticmethod
        def safe_divide(num, den):
            return f"CASE WHEN {den} = 0 THEN NULL ELSE {num} * 1.0 / {den} END"

    env.globals["m"] = Macros()
    records = []
    for config in CONFIGS:
        stack = []
        def ref(name):
            if name in stack:
                raise ValueError(f"cyclic ref {name}")
            stack.append(name)
            try:
                return "(" + render(raw_models[name]) + ")"
            finally:
                stack.pop()
        def render(raw):
            return env.from_string(raw).render(ref=ref, var=lambda k, default=None: config.get(k, default))
        raw_models = {m: (root / "models" / f"{m}.sql").read_text(encoding="utf-8") for m in MODELS}
        for model in MODELS:
            raw = raw_models[model]
            try:
                expanded = render(raw)
            except Exception as exc:
                records.append({"model": model, "config": config, "render_error": f"{type(exc).__name__}: {exc}"})
                continue
            rec = {"model": model, "config": config, "expanded_sql": expanded}
            try:
                raw_edges = norm(extract_static_lineage(raw, schema, dialect="sqlite"))
                rec["raw_static_status"] = "parsed"
                rec["raw_static_edges"] = len(raw_edges)
            except Exception as exc:
                rec["raw_static_status"] = f"error: {type(exc).__name__}"
                rec["raw_static_edges"] = 0
            try:
                static = norm(extract_static_lineage(expanded, schema, dialect="sqlite"))
                rec["expanded_static_status"] = "parsed"
            except Exception as exc:
                rec["expanded_static_status"] = f"error: {type(exc).__name__}"
                records.append(rec); continue
            try:
                ref_out = reference_edges({"sql": expanded, "tables": tables})
                lit_out = literal_edges({"sql": expanded, "tables": tables}, budget=3)
                b10_out = limited_edges({"sql": expanded, "tables": tables},
                                        ["CELL_VALUE", "VALUE_TO_NULL", "NULL_TO_VALUE"], 10)
                ref_edges = norm(ref_out["edges"]); lit = norm(lit_out["edges"]); b10 = norm(b10_out["edges"])
                silver = ref_edges | lit
                methods = {
                    "expanded_static": (static, 0),
                    "static_plus_oracle": (static | b10, b10_out["executions"]),
                    "static_plus_literal": (static | lit, lit_out["executions"]),
                    "static_plus_literal_oracle": (static | lit | b10, lit_out["executions"] + b10_out["executions"]),
                }
                rec["silver_edges"] = len(silver)
                rec["methods"] = {}
                for name, (pred, cost) in methods.items():
                    m = metrics(pred, silver); m["executions"] = cost
                    rec["methods"][name] = m
            except Exception as exc:
                rec["oracle_status"] = f"error: {type(exc).__name__}: {exc}"
            records.append(rec)

    summary = {}
    for name in ["expanded_static", "static_plus_oracle", "static_plus_literal", "static_plus_literal_oracle"]:
        rows = [r for r in records if "methods" in r]
        if not rows:
            continue
        summary[name] = {
            "n": len(rows),
            "macro_f1": sum(r["methods"][name]["f1"] for r in rows) / len(rows),
            "macro_recall": sum(r["methods"][name]["recall"] for r in rows) / len(rows),
            "mean_executions": sum(r["methods"][name]["executions"] for r in rows) / len(rows),
            "micro_tp": sum(r["methods"][name]["tp"] for r in rows),
            "micro_outside": sum(r["methods"][name]["outside"] for r in rows),
            "micro_missing": sum(r["methods"][name]["missing"] for r in rows),
        }
    summary["raw_static_errors"] = sum(1 for r in records if r.get("raw_static_status") != "parsed")
    summary["n_records"] = len(records)
    Path("results/p3_dbt_ext.json").write_text(json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
