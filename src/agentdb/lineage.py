"""Static column-level lineage extraction using sqlglot (syntactic baseline)."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.lineage import Node, lineage

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_alias_map(sql: str, dialect: str = "duckdb") -> dict[str, str]:
    """Map table aliases (and table names) to real table names."""
    tree = sqlglot.parse_one(sql, read=dialect)
    mapping: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        name = table.name
        mapping[name] = name
        alias = table.alias
        if alias:
            mapping[alias] = name
    return mapping


def _leaves(node: Node) -> list[Node]:
    if not node.downstream:
        return [node]
    out: list[Node] = []
    for child in node.downstream:
        out.extend(_leaves(child))
    return out


def _leaf_edge(leaf: Node, alias_map: dict[str, str]) -> tuple[str, str] | None:
    """Resolve a lineage leaf to (table, column); return None for literals."""
    name = str(leaf.name or "")
    expr = leaf.expression
    # Base table node: expression is exp.Table, leaf name is "table.column" or "alias.column".
    if isinstance(expr, exp.Table):
        table = expr.name
        if "." in name:
            col = name.rsplit(".", 1)[-1]
        else:
            col = name
        if not _IDENT_RE.match(col):
            return None
        return (table, col)
    if "." in name:
        prefix, col = name.rsplit(".", 1)
        if not _IDENT_RE.match(col):
            return None
        table = alias_map.get(prefix, prefix)
        return (table, col)
    if _IDENT_RE.match(name):
        return (name, name)  # unqualified leaf: keep as-is; callers can filter
    return None


def extract_static_lineage(
    sql: str, schema: dict[str, dict[str, str]], dialect: str = "duckdb"
) -> set[tuple[str, str, str]]:
    """Return syntactic lineage edges as (output_col, source_table, source_col).

    This is the *baseline* path: it trusts the parse tree and does not execute.
    """
    alias_map = build_alias_map(sql, dialect=dialect)
    trees = lineage(None, sql, schema=schema, dialect=dialect)
    edges: set[tuple[str, str, str]] = set()
    for out_col, node in trees.items():
        for leaf in _leaves(node):
            resolved = _leaf_edge(leaf, alias_map)
            if resolved is None:
                continue
            table, col = resolved
            if table not in schema:
                # Unqualified/unknown table: leave it out rather than invent one.
                continue
            edges.add((out_col, table, col))
    return edges
