"""Minimal local Ollama client for the LLM lineage baseline.

The pilot uses a local model so no external API key or egress is involved.
If Ollama is unreachable, the caller must mark the run UNAVAILABLE rather than
fabricate predictions.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
_JSON_ARRAY_RE = re.compile(r"\[[^\[\]]*(?:\][^\[\]]*)*\]", re.S)


class LLMUnavailable(RuntimeError):
    pass


def _extract_json_array(text: str) -> list[list[str]]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = fenced.group(1).strip() if fenced else text
    data = None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("["), candidate.rfind("]")
        if start != -1 and end > start:
            try:
                data = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, list):
        return []
    if not isinstance(data, list):
        return []
    edges: list[list[str]] = []
    for item in data:
        if isinstance(item, list) and len(item) == 3 and all(isinstance(x, str) for x in item):
            edges.append(item)
    return edges


def predict_edges(
    sql: str,
    schema: dict[str, dict[str, str]],
    *,
    model: str = "qwen3:8b",
    seed: int = 42,
    timeout_s: int = 120,
) -> set[tuple[str, str, str]]:
    prompt = (
        "You are a data lineage expert. Given the table schema and the SQL query, "
        "return ONLY a JSON array of 3-element arrays: "
        "[output_column, source_table, source_column]. "
        "Include every source column that can influence the output column. "
        "Do not include literals or tables that do not exist in the schema.\n\n"
        f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"SQL: {sql}\n"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "seed": seed},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f"Ollama unavailable: {exc}") from exc
    raw = str(body.get("response", ""))
    edges = _extract_json_array(raw)
    return {tuple(edge) for edge in edges if edge[1] in schema}
