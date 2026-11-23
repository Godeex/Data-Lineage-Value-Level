import json
from pathlib import Path
import numpy as np

def paired(a,b,n_boot=10000,seed=42):
    rng=np.random.default_rng(seed); diff=a-b
    idx=rng.integers(0,len(diff),size=(n_boot,len(diff))); means=diff[idx].mean(axis=1)
    lo,hi=np.percentile(means,[2.5,97.5])
    p=2*min(float((means<=0).mean()),float((means>=0).mean()))
    return {"n":int(len(diff)),"mean_a":float(a.mean()),"mean_b":float(b.mean()),
            "mean_diff":float(diff.mean()),"ci95":[float(lo),float(hi)],"p_two_sided":float(min(1,p))}

d=json.load(open('results/heldout_gold.json'))['per_query']
pairs=[('evolving_vs_fixed',"evolving","fixed_hybrid"),
       ('literal_vs_fixed',"literal","fixed_hybrid"),
       ('literal_union_evolving_vs_fixed',"literal_union_evolving","fixed_hybrid"),
       ('literal_union_evolving_vs_evolving',"literal_union_evolving","evolving"),
       ('literal_union_evolving_vs_machine',"literal_union_evolving","machine_reference"),
       ('predicate_aware_vs_fixed',"predicate_aware","fixed_hybrid")]
def s(name,key): return {r['qid']:r[key] for r in d[name]}
out={}
for label,a,b in pairs:
    af,bf=s(a,'f1'),s(b,'f1'); ar,br=s(a,'recall'),s(b,'recall')
    q=sorted(set(af)&set(bf))
    out[label]={'f1':paired(np.array([af[x] for x in q]),np.array([bf[x] for x in q])),
                'recall':paired(np.array([ar[x] for x in q]),np.array([br[x] for x in q]))}
Path('results/heldout_stats.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
print(json.dumps(out,ensure_ascii=False,indent=1))
