import importlib.util,json,sqlite3,sys
from pathlib import Path
import os
LX=os.environ.get("LINEAGEX_PATH","/tmp/lxenv")
spec=importlib.util.spec_from_file_location("clnc",f"{LX}/lineagex/ColumnLineageNoConn.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
DB=Path(os.environ.get('AGENTDB_DB_DIR','/data/gx/spider/db'))
def schema(db):
 c=sqlite3.connect(str(db)); out={}
 for (t,) in c.execute("select name from sqlite_master where type='table'"):
  out[t]=[r[1] for r in c.execute(f'pragma table_info("{t}")')]
 c.close(); return out
def norm(s):
 s=s.strip().replace('"','')
 if '.' in s:
  t,c=s.split('.',1); return (t.casefold(),c.casefold())
 return ('',s.casefold())
def actual_outputs(db,sql):
 c=sqlite3.connect(str(db))
 try: cur=c.execute(sql); return [str(d[0]).casefold().strip() for d in (cur.description or [])]
 except Exception: return []
 finally: c.close()
def map_out(name,actual):
 n=str(name).casefold().strip()
 if n in actual: return n
 for a in actual:
  if a.startswith(n+'(') or a.startswith(n+' ') or a==n: return a
 return n
rows=[]
for path in ['data/spider_main.jsonl','results/confirmation_queries.jsonl']:
 for line in open(path):
  r=json.loads(line)
  if any(x['qid']==r['qid'] for x in rows): continue
  rows.append(r)
out=[]
for r in rows:
 db=DB/f"{r['db_id']}.sqlite"
 try:
  o=mod.ColumnLineageNoConn(sql=r['sql'],dialect='sqlite',input_table_dict=schema(db))
  actual=actual_outputs(db,r['sql']); edges=set()
  for outcol,(direct,indirect) in o.column_dict.items():
   ocol=map_out(outcol,actual)
   for s in direct+indirect:
    t,c=norm(s); edges.add((ocol,t,c))
  out.append({'qid':r['qid'],'edges':sorted(edges),'err':None})
 except Exception as e:
  out.append({'qid':r['qid'],'edges':[],'err':f'{type(e).__name__}: {e}'})
with open('results/lineagex_edges.jsonl','w') as fh:
 for r in out: fh.write(json.dumps(r)+'\n')
print('queries',len(out),'errors',sum(1 for r in out if r['err']))
for r in out[:3]: print(r['qid'],r['edges'][:5],r['err'])
