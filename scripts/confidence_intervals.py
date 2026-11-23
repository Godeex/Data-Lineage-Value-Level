"""Bootstrap 95% CIs for macro F1 and oracle wall-clock on the confirmation set."""
from __future__ import annotations
import json, os, random, time
from pathlib import Path
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

ROOT=Path(__file__).resolve().parents[1]; DB=Path(os.environ.get('AGENTDB_DB_DIR','/data/gx/spider/db'))
def boot(vals, n=10000, seed=42):
 rng=random.Random(seed); out=[]
 for _ in range(n): out.append(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals)))/len(vals))
 out.sort(); return out[int(.025*n)], out[int(.975*n)-1]
def f1(pred,pos,neg):
 tp=len(pred&pos); fp=len(pred&neg); fn=len(pos-pred); p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
 return 2*p*r/(p+r) if p+r else 0
# discovery per-query
gd=json.load(open('results/gold_eval.json'))['per_query']
disc={k:[r['f1'] for r in gd[k]] for k in ['fixed_hybrid','oracle_literal','literal_union_all']}
# confirmation per-query
gold={}
for l in open('results/confirmation_gold_final.jsonl'):
 r=json.loads(l); gold.setdefault(r['qid'],{'P':set(),'N':set(),'U':set()})
 d=r['decision'].upper()
 tgt='P' if d=='POSITIVE' else 'N' if d=='NEGATIVE' else 'U'
 gold[r['qid']][tgt].add((r['output_column'].casefold(),r['source_table'].casefold(),r['source_column'].casefold()))
preds={json.loads(l)['qid']:json.loads(l) for l in open('results/confirmation_queries.jsonl')}
sealed={json.loads(l)['qid']:json.loads(l) for l in open('annotations/confirmation/results/sealed/predictions.jsonl')}
conf={k:[] for k in ['fixed','literal','union']}
for q,p in sealed.items():
 for key,field in [('fixed','fixed_edges'),('literal','literal_edges'),('union','union_edges')]:
  e={(a.casefold(),b.casefold(),c.casefold()) for a,b,c in p[field]}
  conf[key].append(f1(e,gold[q]['P'],gold[q]['N']))
out={'discovery':{k:{'mean':sum(v)/len(v),'ci95':boot(v)} for k,v in disc.items()},
     'confirmation':{k:{'mean':sum(v)/len(v),'ci95':boot(v)} for k,v in conf.items()}}
# wall clock on 10 confirmation queries
qs=list(preds.values())[:10]; times=[]
for q in qs:
 db=DB/f"{q['db_id']}.sqlite"; tables=load_sqlite_tables(db,max_rows=30); script={'sql':q['sql'],'tables':tables}
 t=time.perf_counter(); limited_edges(script,['CELL_VALUE'],3); t1=time.perf_counter();
 literal_edges(script,budget=3); t2=time.perf_counter()
 times.append(((t1-t)*1000,(t2-t1)*1000))
out['latency_ms']={'n':len(times),'cell_mean':sum(x[0] for x in times)/len(times),'literal_mean':sum(x[1] for x in times)/len(times)}
Path('results/confidence_intervals.json').write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
