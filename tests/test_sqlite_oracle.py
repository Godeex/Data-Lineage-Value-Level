import json
from pathlib import Path

from agentdb.sqlite_oracle import limited_edges, reference_edges

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "synthetic_pipelines.json"


def _scripts():
    return {s["id"]: s for s in json.loads(FIXTURE.read_text(encoding="utf-8"))["scripts"]}


def test_reference_matches_gold_for_projection():
    script = _scripts()["syn-01-projection"]
    out = reference_edges({"sql": script["sql"], "tables": script["tables"]})
    expected = {tuple(edge) for edge in script["ground_truth"]}
    assert out["edges"] == expected


def test_limited_budget_one_matches_gold_for_projection():
    script = _scripts()["syn-01-projection"]
    out = limited_edges({"sql": script["sql"], "tables": script["tables"]}, ["CELL_VALUE"], 1)
    expected = {tuple(edge) for edge in script["ground_truth"]}
    assert out["edges"] == expected


def test_empty_result_has_no_reference_edges():
    script = _scripts()["syn-01-projection"]
    empty = {"sql": "SELECT id, amount FROM src_a WHERE 1 = 0", "tables": script["tables"]}
    out = reference_edges(empty)
    assert out["edges"] == set()


def test_limit_one_only_observes_first_row():
    script = _scripts()["syn-01-projection"]
    limit = {"sql": "SELECT id, amount FROM src_a ORDER BY id LIMIT 1", "tables": script["tables"]}
    out = limited_edges(limit, ["CELL_VALUE"], 1)
    # Only row 1 is tested; id/amount of row 1 should be observed.
    assert ("id", "src_a", "id") in out["edges"]
    assert ("amount", "src_a", "amount") in out["edges"]
