"""Fixture loading and schema helpers for the P0 pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def load_fixture(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "scripts" not in data or not data["scripts"]:
        raise ValueError("fixture must contain a non-empty scripts list")
    return data


def schema_for(script: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {name: dict(spec["columns"]) for name, spec in script["tables"].items()}


def gold_edges(script: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {tuple(edge) for edge in script["ground_truth"]}
