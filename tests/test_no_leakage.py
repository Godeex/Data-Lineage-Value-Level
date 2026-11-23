import copy
from pathlib import Path

from agentdb import data as data_mod
from agentdb.lineage import extract_static_lineage

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "synthetic_pipelines.json"


def test_predictions_do_not_use_ground_truth():
    """Predictions must be computable after deleting the gold labels."""
    for script in data_mod.load_fixture(FIXTURE)["scripts"]:
        with_gold = extract_static_lineage(script["sql"], data_mod.schema_for(script))
        stripped = copy.deepcopy(script)
        stripped.pop("ground_truth", None)
        without_gold = extract_static_lineage(stripped["sql"], data_mod.schema_for(stripped))
        assert with_gold == without_gold, script["id"]
