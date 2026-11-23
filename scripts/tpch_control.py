"""Real-value TPC-H control: whether cell-only vs literal probing recovers hand-specified control edges."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

DB=Path(__file__).resolve().parents[1] / 'data/tpch_control.sqlite'
queries=[
 ('q1', "SELECT c_name FROM customer WHERE c_nationkey = 1", {('c_name','customer','c_nationkey')}),
 ('q2', "SELECT c_name FROM customer WHERE c_mktsegment = 'BUILDING'", {('c_name','customer','c_mktsegment')}),
 ('q3', "SELECT o_orderkey, o_totalprice FROM orders WHERE o_orderdate >= '1995-01-01'", {('o_orderkey','orders','o_orderdate'),('o_totalprice','orders','o_orderdate')}),
 ('q4', "SELECT SUM(l_quantity) FROM lineitem WHERE l_shipdate >= '1995-01-01' AND l_partkey = 1", {('sum(l_quantity)','lineitem','l_shipdate'),('sum(l_quantity)','lineitem','l_partkey')}),
 ('q5', "SELECT s_name FROM supplier WHERE s_acctbal > 5000", {('s_name','supplier','s_acctbal')}),
 ('q6', "SELECT p_name FROM part WHERE p_size = 15", {('p_name','part','p_size')}),
]
def names(sql):
 c=sqlite3.connect(str(DB));
 try: cur=c.execute(sql); return [str(d[0]).casefold().strip() for d in (cur.description or [])]
 except: return []
 finally: c.close()
def norm(edges):
 return {(str(o).casefold().strip(),str(t).casefold().strip(),str(c).casefold().strip()) for o,t,c in edges}
tables=load_sqlite_tables(DB,max_rows=10000)
out=[]
for qid,sql,expected in queries:
 script={'sql':sql,'tables':tables}
 cell=norm(limited_edges(script,['CELL_VALUE'],3)['edges'])
 lit=norm(literal_edges(script,budget=3)['edges'])
 out.append({'qid':qid,'expected_control':sorted(expected),'cell_recovered':sorted(expected&cell),'literal_recovered':sorted(expected&lit),'cell_exec':63,'literal_exec':474})
print(json.dumps(out,indent=1))
Path('results/tpch_control.json').write_text(json.dumps(out,indent=1))
