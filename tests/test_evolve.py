from agentdb.evolve import norm, prf, split_by_db


def test_norm_casefolds():
    assert norm([("A", "T", "C")]) == {("a", "t", "c")}


def test_prf_perfect_and_partial():
    gold = {("a", "t", "c"), ("b", "t", "d")}
    assert prf(gold, gold)[2] == 1.0
    p, r, f1 = prf({("a", "t", "c")}, gold)
    assert p == 1.0 and r == 0.5


def test_split_by_db_deterministic():
    rows = [{"db_id": f"db{i}", "qid": f"q{i}"} for i in range(20)]
    a = split_by_db(rows, seed=42)
    b = split_by_db(rows, seed=42)
    assert {k: len(v) for k, v in a.items()} == {k: len(v) for k, v in b.items()}
    assert set(r["db_id"] for r in a["train"]).isdisjoint(set(r["db_id"] for r in a["test"]))
