import json
from pathlib import Path

from agentdb import data as data_mod
from agentdb.lineage import extract_static_lineage

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "synthetic_pipelines.json"


def _scripts():
    return data_mod.load_fixture(FIXTURE)["scripts"]


def test_static_lineage_matches_gold_for_projection_and_case():
    for script in _scripts():
        if script["id"] not in {"syn-01-projection", "syn-02-case"}:
            continue
        schema = data_mod.schema_for(script)
        pred = extract_static_lineage(script["sql"], schema)
        assert pred == data_mod.gold_edges(script)


def test_static_lineage_matches_gold_for_cte_and_coalesce_and_aggregate():
    for script in _scripts():
        if script["id"] in {"syn-01-projection", "syn-02-case"}:
            continue
        schema = data_mod.schema_for(script)
        pred = extract_static_lineage(script["sql"], schema)
        assert pred == data_mod.gold_edges(script), script["id"]
