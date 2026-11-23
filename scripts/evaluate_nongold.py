"""Evaluate fixed hybrid vs literal probing on 100 non-gold main queries."""
import json
import os
from pathlib import Path
from collections import defaultdict
from agentdb.spider import load_sqlite_tables
from agentdb.sqlite_oracle import limited_edges, literal_edges

def norm(edges):
    return {(str(a).casefold(), str(b).casefold(), str(c).casefold()) for a,b,c in edges}

def prf(pred, gold):
    tp=len(pred&gold); fp=len(pred-gold); fn=len(gold-pred)
    p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
    f=2*p*r/(p+r) if p+r else 0
    return tp,fp,fn,p,r,f

main=[json.loads(l) for l in open('data/spider_main.jsonl')]
gold={json.loads(l)['qid'] for l in open('annotations/discovery/package/sample_30.jsonl')}
p1={json.loads(l)['qid']:json.loads(l) for l in open('results/p1_coverage.jsonl')}
rows=[r for r in main if r['qid'] not in gold and r['qid'] in p1]
out=defaultdict(list)
for r in rows:
    tables=load_sqlite_tables(Path(os.environ.get('AGENTDB_DB_DIR','/data/gx/spider/db'))/f"{r['db_id']}.sqlite",max_rows=30)
    script={'sql':r['sql'],'tables':tables}
    ref=norm(p1[r['qid']]['ref_edges']); static=norm(p1[r['qid']]['static_edges'])
    b3=norm(limited_edges(script,['CELL_VALUE'],3)['edges'])
    lit_out=literal_edges(script,budget=3); lit=norm(lit_out['edges'])
    preds={'fixed_hybrid':static|b3,'literal':lit,'literal_union_fixed':static|b3|lit}
    for name,pred in preds.items():
        tp,fp,fn,P,R,F=prf(pred,ref)
        out[name].append({'qid':r['qid'],'category':r['category'],'tp':tp,'fp':fp,'fn':fn,
                          'precision':P,'recall':R,'f1':F,'executions': (60 if name=='fixed_hybrid' else lit_out['executions'])})
summary={}
for name,recs in out.items():
    tp=sum(x['tp'] for x in recs); fp=sum(x['fp'] for x in recs); fn=sum(x['fn'] for x in recs)
    P=tp/(tp+fp) if tp+fp else 0; R=tp/(tp+fn) if tp+fn else 0; F=2*P*R/(P+R) if P+R else 0
    summary[name]={'n':len(recs),'micro_tp':tp,'micro_fp':fp,'micro_fn':fn,
                   'micro_precision':P,'micro_recall':R,'micro_f1':F,
                   'mean_executions':sum(x['executions'] for x in recs)/len(recs)}
Path('results/nongold_eval.json').write_text(json.dumps({'summary':summary,'per_query':dict(out)},ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=1))
