import json
from pathlib import Path

from agentdb import data as data_mod
from agentdb.metrics import coverage
from agentdb.oracle import oracle_edges

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "synthetic_pipelines.json"


def test_oracle_matches_gold_and_is_deterministic():
    for script in data_mod.load_fixture(FIXTURE)["scripts"]:
        first, meta1 = oracle_edges(script)
        second, meta2 = oracle_edges(script)
        assert first == second, script["id"]
        assert meta1 == meta2
        assert first == data_mod.gold_edges(script), script["id"]


def test_oracle_coverage_is_one_on_fixture():
    for script in data_mod.load_fixture(FIXTURE)["scripts"]:
        observed, _ = oracle_edges(script)
        cov = coverage(observed, data_mod.gold_edges(script))
        assert cov["coverage"] == 1.0, script["id"]
        assert cov["false_negative_rate"] == 0.0, script["id"]
