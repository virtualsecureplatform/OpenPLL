"""Run exact GMP capacitance congruence on a pinned local-C model."""
import argparse,json,os,time
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from project_prototype_fixed_rail_C_v2 import project,RAILS,FIXED
from audit_hierarchical_capacitance import number
from compiled_charge import execute
from resources import lease,identity


def run(source,binary,output,seconds,corner="nom",attachment="driver"):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    model=source/(corner+'_'+attachment+'.spice')
    if r['artifacts'].get(str(model))!=sha(model):raise ValueError('model mismatch')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+seconds+60
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    # Use exact decimal-rational parsing, with no floating-point conversion.
    from fractions import Fraction as F
    pairs=defaultdict(F)
    for line in model.read_text().splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat'):pairs[tuple(sorted(f[1:3]))]+=number(f[3])
    pairs=project(pairs,set(RAILS));nodes=sorted({n for edge in pairs for n in edge if n!=FIXED});ids={n:i for i,n in enumerate(nodes)};edges=output/'edges.tsv'
    with edges.open('w')as f:
        f.write(f'{len(nodes)} {len(pairs)}\n')
        for (a,b),c in pairs.items():
            if a==FIXED:a,b=b,a
            f.write(f'{ids[a]} {ids.get(b,-1)} {c}\n')
    folder=Path(__file__).resolve().parent;cpp=folder.parent.parent/'tools/capacitance_energy/exact_sparse_ldl.cpp'
    pins={str(p):sha(p)for p in [receipt,model,binary,cpp,Path(__file__).resolve(),folder/'project_prototype_fixed_rail_C_v2.py',folder/'audit_hierarchical_capacitance.py',edges]}
    report=output/'report.json';save(output/'input_manifest.json',dict(input_sha256=pins))
    with lease(1,8,deadline):execute([binary,edges,report,str(seconds)],output/'native.log',deadline,8)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},result=json.loads(report.read_text()),method='exact GMP rational sparse LDL congruence',fixed_supply_scope=True,models_modified=False,native_simulation_allowed=False,physical_RC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--seconds',type=int,default=120);p.add_argument('--remaining',action='store_true');a=p.parse_args()
    if a.remaining:
        a.output.mkdir(parents=True,exist_ok=False)
        save(a.output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
        receipts=[]
        for corner,attachment in [('nom','farthest'),('min','driver'),('min','farthest'),('max','driver'),('max','farthest')]:
            save(a.output/'status.json',dict(state='exact_C_GMP_running',corner=corner,attachment=attachment,release_ready=False))
            dest=a.output/(corner+'_'+attachment);run(a.source.resolve(),a.binary.resolve(),dest.resolve(),a.seconds,corner,attachment);receipts.append(dest.resolve()/'assessment.json')
        save(a.output/'assessment.json',dict(artifacts={str(p):sha(p)for p in receipts},results=[json.loads(p.read_text())['result']for p in receipts],release_ready=False))
    else:run(a.source.resolve(),a.binary.resolve(),a.output.resolve(),a.seconds)
