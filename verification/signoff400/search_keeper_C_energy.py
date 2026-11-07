"""Search emitted C energy numerically, then verify the candidate exactly."""
import argparse,json,os,time
from fractions import Fraction as F
from collections import defaultdict
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from audit_hierarchical_capacitance import number
from project_prototype_fixed_rail_C_v2 import project,RAILS,FIXED
from audit_local_C_principal_energy import witness
from compiled_charge_v2 import execute
from resources import lease,identity


def run(source,binary,attachment,cpu,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not all(r[k]for k in ['full_parent_C_retained','DCO_internal_wire_R_inserted','BBPD_internal_wire_R_inserted','digital_internal_wire_R_inserted']):raise ValueError('complete all-macro composition required')
    model=source/(attachment+'.spice')
    if r['artifacts'].get(str(model))!=sha(model):raise ValueError('emitted model changed')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+420
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=8))
    pairs=defaultdict(F)
    for line in model.read_text().splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat'):pairs[tuple(sorted(f[1:3]))]+=number(f[3])
    pairs=project(pairs,set(RAILS));nodes=sorted({n for pair in pairs for n in pair if n!=FIXED});ids={n:i for i,n in enumerate(nodes)};edges=output/'edges.tsv'
    with edges.open('x')as f:
        f.write(f'{len(nodes)} {len(pairs)}\n')
        for (a,b),c in pairs.items():
            if a==FIXED:a,b=b,a
            f.write(f'{ids[a]} {ids.get(b,-1)} {c}\n')
    folder=Path(__file__).resolve().parent;files=[receipt,model,binary,edges,Path(__file__).resolve(),ROOT/'tools/capacitance_energy/search_sparse_C_energy.cpp',folder/'audit_local_C_principal_energy.py',folder/'project_prototype_fixed_rail_C_v2.py',folder/'audit_hierarchical_capacitance.py'];pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins,attachment=attachment,nodes=len(nodes),pairs=len(pairs)))
    try:
        principal=witness(pairs);save(output/'principal.json',principal)
        artifacts={str(output/'principal.json'):sha(output/'principal.json')}
        if principal['indefiniteness_proved']:result=principal
        else:
            vector=output/'voltage_integers.tsv';report=output/'search.report.json';save(output/'status.json',dict(state='searching_C_energy_candidate',release_ready=False))
            with lease(1,8,deadline):execute([binary,edges,vector,report,'300'],output/'native.log',deadline,8)
            entries=list(map(int,vector.read_text().split()))
            if len(entries)!=len(nodes)+1 or entries[0]!=len(nodes):raise ValueError('candidate voltage dimension differs')
            values=dict(zip(nodes,entries[1:]));values[FIXED]=0
            # Independently stamp the exact source capacitor values. Search
            # coefficients, normalized matrix and floating energy are not used.
            energy=sum((c*(values[a]-values[b])**2 for (a,b),c in pairs.items()),F())/10**18
            result=dict(indefiniteness_proved=energy<0,exact_twice_energy_J=str(energy),voltage_denominator=10**9,all_source_pairs_independently_stamped=True,nonnegative_candidate_is_not_PSD_certificate=True)
            artifacts.update({str(p):sha(p)for p in [vector,report]})
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,attachment=attachment,result=result,passivity_certified=False,intrinsic_device_C_included=False,models_modified=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='exact_candidate_energy_verified',indefiniteness_proved=result['indefiniteness_proved'],release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_conclusion',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--attachment',choices=['driver','farthest'],required=True);p.add_argument('--cpu',type=int,required=True);a=p.parse_args();run(a.source.resolve(),a.binary.resolve(),a.attachment,a.cpu,a.output.resolve())
