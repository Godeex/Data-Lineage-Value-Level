from agentdb.sqlite_oracle import literal_edges, sql_literals


def test_sql_literals_extracts_numbers_and_strings():
    lits = sql_literals("SELECT count(*) FROM concert WHERE YEAR = 2014 OR YEAR = 2015")
    assert "2014" in [str(x) for x in lits]
    assert 2014 in lits
    lits2 = sql_literals("SELECT * FROM singer WHERE country = 'France'")
    assert "France" in lits2


def test_literal_probe_recovers_predicate_column():
    script = {
        "sql": "SELECT count(*) FROM src_a WHERE id = 2",
        "tables": {"src_a": {"columns": {"id": "INT", "amount": "INT"},
                              "rows": [[1, 10], [2, 20]]}},
    }
    out = literal_edges(script, budget=3)
    assert ("count(*)", "src_a", "id") in out["edges"]


def test_literal_probe_budget_none_is_exhaustive():
    script = {
        "sql": "SELECT max(amount) FROM src_a WHERE id = 4",
        "tables": {"src_a": {"columns": {"id": "INT", "amount": "INT"},
                              "rows": [[1, 10], [2, 20], [3, 30], [4, 40]]}},
    }
    budgeted = literal_edges(script, budget=3)
    exhaustive = literal_edges(script, budget=None)
    assert ("max(amount)", "src_a", "amount") not in budgeted["edges"]
    assert ("max(amount)", "src_a", "amount") in exhaustive["edges"]


def test_literal_probe_recovers_case_extreme():
    script = {
        "sql": (
            "SELECT *, CASE WHEN \"avg(amount)\" > 0 THEN 'pos' ELSE 'nonpos' END AS bucket "
            "FROM (SELECT avg(amount) AS \"avg(amount)\", max(amount) AS \"max(amount)\" FROM src_a) AS base"
        ),
        "tables": {"src_a": {"columns": {"id": "INT", "amount": "INT"},
                              "rows": [[1, 10], [2, 20], [3, 30]]}},
    }
    out = literal_edges(script, budget=3)
    assert ("bucket", "src_a", "amount") in out["edges"]
