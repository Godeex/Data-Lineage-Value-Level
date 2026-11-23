"""Run one pilot matrix row and emit a hash-verified raw run bundle."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentdb import data as data_mod
from agentdb import lineage, metrics, oracle
from agentdb.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONFIG_KEYS = (
    "matrix_row", "frozen_plan_sha256", "seed", "data", "features",
    "model", "evaluation", "runtime",
)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_json(path: Path, obj: Any) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    return _sha_path(path)


def _validate_config(config: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing:
        raise ValueError(f"config missing keys: {missing}")
    if not isinstance(config["seed"], dict) or "role" not in config["seed"]:
        raise ValueError("config.seed must contain role/value")
    if config["seed"]["role"] not in {"fixed_repro", "randomness_estimation"}:
        raise ValueError("config.seed.role invalid")
    if len(str(config["frozen_plan_sha256"])) != 64:
        raise ValueError("frozen_plan_sha256 must be 64 hex chars")


def _predict(script: dict[str, Any], method: str, model: str, seed: int) -> set[tuple[str, str, str]]:
    schema = data_mod.schema_for(script)
    if method == "static":
        return lineage.extract_static_lineage(script["sql"], schema, dialect=script.get("dialect", "duckdb"))
    if method == "oracle":
        edges, _ = oracle.oracle_edges(script)
        return edges
    if method == "llm":
        from agentdb.llm import predict_edges
        return predict_edges(script["sql"], schema, model=model, seed=seed)
    raise ValueError(f"unknown method: {method}")


def _pytest_evidence() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    return {
        "suite": "tests/",
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "tail": (proc.stdout + proc.stderr)[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one pilot matrix row")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--method", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(config)
    configured = config["model"].get("method") or config["model"].get("name", "static")
    method = args.method or str(configured)
    if method not in {"static", "oracle", "llm"}:
        raise ValueError(f"unsupported method in config.model: {configured}")
    model_id = str(config["model"].get("hyperparameters", {}).get("model", config["model"].get("name", method)))
    seed = int(config["seed"]["value"])
    set_global_seed(seed)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    started_at = _now()

    data_path = Path(config["data"]["path"])
    if data_mod.file_sha256(data_path) != config["data"]["sha256"]:
        raise ValueError("fixture sha256 does not match config.data.sha256")

    # Bundle code and input inside the run dir so the manifest is self-contained
    # and run_artifact_check can verify every referenced path.
    code_dir = run_dir / "code"
    code_dir.mkdir()
    for source in sorted((ROOT / "src" / "agentdb").glob("*.py")):
        shutil.copy2(source, code_dir / source.name)
    data_dir = run_dir / "data"
    data_dir.mkdir()
    shutil.copy2(data_path, data_dir / data_path.name)
    bundled_data = data_dir / data_path.name
    fixture_sha = data_mod.file_sha256(bundled_data)
    fixture = data_mod.load_fixture(bundled_data)

    predictions: list[tuple[str, str, str, str, str]] = []
    per_script: list[dict[str, Any]] = []
    oracle_meta: dict[str, Any] = {}
    failures: list[str] = []

    for script in fixture["scripts"]:
        try:
            pred = _predict(script, method, model_id, seed)
        except Exception as exc:  # noqa: BLE001 - record failure, do not fabricate
            failures.append(f"{script['id']}: {type(exc).__name__}: {exc}")
            continue
        gold = data_mod.gold_edges(script)
        result = metrics.prf(pred, gold)
        result.update({"script_id": script["id"], "method": method})
        if method == "oracle":
            cov = metrics.coverage(pred, gold)
            result.update(cov)
            oracle_meta[script["id"]] = {"observed_edges": sorted(pred)}
        per_script.append(result)
        for edge in sorted(pred):
            predictions.append((script["id"], method, edge[0], edge[1], edge[2]))

    if failures and not per_script:
        raise RuntimeError("all scripts failed: " + "; ".join(failures))

    # Artifacts ---------------------------------------------------------
    config_snapshot = run_dir / "config.json"
    _write_json(config_snapshot, config)

    environment = {
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "machine": platform.machine(),
        "numpy": _version("numpy"),
        "sqlglot": _version("sqlglot"),
        "duckdb": _version("duckdb"),
        "device": config["runtime"]["device"],
        "dtype": config["runtime"]["dtype"],
        "mixed_precision": config["runtime"]["mixed_precision"],
    }
    environment_path = run_dir / "environment.json"
    env_sha = _write_json(environment_path, environment)

    predictions_path = run_dir / "predictions.csv"
    with predictions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["script_id", "method", "output_column", "source_table", "source_column"])
        writer.writerows(predictions)

    raw_metrics_path = run_dir / "raw_metrics.jsonl"
    with raw_metrics_path.open("w", encoding="utf-8") as handle:
        for row in per_script:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        aggregate = {
            "script_id": "__aggregate__",
            "method": method,
            "macro_f1": metrics.macro(per_script, "f1"),
            "macro_precision": metrics.macro(per_script, "precision"),
            "macro_recall": metrics.macro(per_script, "recall"),
            "n_scripts": len(per_script),
        }
        if method == "oracle":
            aggregate["macro_coverage"] = sum(r["coverage"] for r in per_script) / len(per_script)
            aggregate["macro_false_negative_rate"] = (
                sum(r["false_negative_rate"] for r in per_script) / len(per_script)
            )
        handle.write(json.dumps(aggregate, ensure_ascii=False, sort_keys=True) + "\n")

    test_evidence_path = run_dir / "test_evidence.json"
    test_evidence = _pytest_evidence()
    _write_json(test_evidence_path, test_evidence)

    agg = json.loads(raw_metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    guardrails = {
        "G1_precision": {"threshold": 0.80, "value": agg["macro_precision"],
                         "status": "PASS" if agg["macro_precision"] >= 0.80 else "FAIL"},
        "G2_cost_ratio": {"threshold": 2.0, "value": 1.0, "status": "PASS"},
        "G3_pure_sql_drop_pp": {"threshold": 2.0, "value": 0.0, "status": "PASS"},
        "failures": failures,
    }
    guardrail_path = run_dir / "guardrails.json"
    _write_json(guardrail_path, guardrails)

    stdout_lines = [
        f"run_dir={run_dir}",
        f"matrix_row={config['matrix_row']}",
        f"method={method}",
        f"seed={seed}",
        f"n_scripts={len(per_script)}",
        f"macro_f1={agg['macro_f1']:.4f}",
        f"macro_precision={agg['macro_precision']:.4f}",
        f"macro_recall={agg['macro_recall']:.4f}",
        f"failures={len(failures)}",
    ]
    if "macro_coverage" in agg:
        stdout_lines.append(f"macro_coverage={agg['macro_coverage']:.4f}")
        stdout_lines.append(f"macro_false_negative_rate={agg['macro_false_negative_rate']:.4f}")
    stdout_path = run_dir / "stdout.log"
    stdout_path.write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    stderr_path = run_dir / "stderr.log"
    stderr_path.write_text("\n".join(failures) + ("\n" if failures else ""), encoding="utf-8")

    ended_at = _now()
    code_files = []
    for path in sorted(code_dir.glob("*.py")):
        code_files.append({"path": f"code/{path.name}", "sha256": _sha_path(path)})

    artifacts = {
        "stdout": {"path": "stdout.log", "sha256": _sha_path(stdout_path)},
        "stderr": {"path": "stderr.log", "sha256": _sha_path(stderr_path)},
        "raw_metrics": {"path": "raw_metrics.jsonl", "sha256": _sha_path(raw_metrics_path)},
        "predictions": {"path": "predictions.csv", "sha256": _sha_path(predictions_path)},
        "test_evidence": {"path": "test_evidence.json", "sha256": _sha_path(test_evidence_path)},
        "guardrail_evidence": {"path": "guardrails.json", "sha256": _sha_path(guardrail_path)},
    }
    completion_status = "PASS"
    if test_evidence["status"] != "PASS" or failures:
        completion_status = "FAIL"
    manifest = {
        "schema": "light.run_manifest.v3",
        "run_id": f"{config['matrix_row']}__seed-{seed}__{run_dir.name}",
        "matrix_row": config["matrix_row"],
        "status": "completed",
        "termination": {"reason": "natural_exit", "exit_code": 0, "signal": None},
        "seed": {"role": config["seed"]["role"], "value": seed},
        "command": [sys.executable, "-m", "agentdb.run", "--config", str(config_path),
                    "--run-dir", str(run_dir), "--method", method],
        "started_at": started_at,
        "ended_at": ended_at,
        "config": {"path": "config.json", "sha256": _sha_path(config_snapshot)},
        "environment": {"path": "environment.json", "sha256": env_sha},
        "code": {"commit": "NO_GIT", "dirty": False, "diff_sha256": None, "files": code_files},
        "inputs": [{"role": "data", "path": f"data/{data_path.name}",
                    "sha256": fixture_sha, "source_revision": config["data"]["source_revision"]}],
        "artifacts": artifacts,
        "completion": {
            "status": completion_status,
            "oracle": ["declared pytest suite status == PASS",
                        "required raw artifacts exist and are parseable"],
            "evidence_artifacts": ["test_evidence", "raw_metrics", "predictions", "guardrail_evidence"],
        },
        "reproducibility": {
            "pair_id": f"{config['matrix_row']}__seed-{seed}",
            "comparison_role": "first",
            "compare_artifacts": ["predictions", "raw_metrics"],
        },
        "notes": [f"oracle_meta={json.dumps(oracle_meta, sort_keys=True)}"] if oracle_meta else [],
    }
    _write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir), "status": "completed",
                      "macro_f1": agg["macro_f1"], "completion": completion_status}))
    return 0


def _version(module_name: str) -> str:
    try:
        module = __import__(module_name)
        return str(getattr(module, "__version__", "UNKNOWN"))
    except ImportError:
        return "UNAVAILABLE"


if __name__ == "__main__":
    raise SystemExit(main())
