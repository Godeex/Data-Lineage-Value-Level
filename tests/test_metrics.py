from agentdb.metrics import coverage, macro, prf


def test_prf_perfect():
    gold = {("a", "t", "c"), ("b", "t", "d")}
    assert prf(gold, gold)["f1"] == 1.0


def test_prf_partial():
    gold = {("a", "t", "c"), ("b", "t", "d")}
    pred = {("a", "t", "c")}
    out = prf(pred, gold)
    assert out["precision"] == 1.0
    assert out["recall"] == 0.5
    assert out["f1"] == 2 * 1.0 * 0.5 / 1.5


def test_macro_averages_scripts():
    rows = [{"f1": 1.0}, {"f1": 0.5}]
    assert macro(rows, "f1") == 0.75


def test_coverage_counts_gold_edges():
    gold = {("a", "t", "c"), ("b", "t", "d")}
    observed = {("a", "t", "c")}
    out = coverage(observed, gold)
    assert out["coverage"] == 0.5
    assert out["false_negative_rate"] == 0.5
