from agentdb.query_sets import classify_sql, primary_category


def test_classify_projection():
    f = classify_sql("SELECT id, amount FROM t")
    assert primary_category(f) == "projection"


def test_classify_join():
    f = classify_sql("SELECT a.id, b.name FROM a JOIN b ON a.id = b.id")
    assert f["join"] is True
    assert primary_category(f) == "join"


def test_classify_aggregate():
    f = classify_sql("SELECT SUM(amount) FROM t")
    assert f["aggregate"] is True
    assert primary_category(f) == "aggregate"


def test_classify_cte_and_case_and_limit():
    f = classify_sql("WITH x AS (SELECT id FROM t) SELECT id, CASE WHEN id > 1 THEN 'a' ELSE 'b' END AS c FROM x LIMIT 1")
    assert f["cte"] is True
    assert f["case"] is True
    assert f["limit"] is True
    assert primary_category(f) == "cte"
