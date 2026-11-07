"""Bound exact full-parent capacitance congruence without changing coefficients."""
import argparse,json,os,time
from pathlib import Path
from fractions import Fraction as F
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from project_prototype_fixed_rail_C_v2 import FIXED


def run(source,binary,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['exact_fixed_voltage_congruence']or not r['complete_original_operator_independently_reparsed']:raise ValueError('complete projected parent required')
    file=source/'dynamic.pairs.jsonl';rows=[json.loads(line)for line in file.open()];nodes=sorted({n for row in rows for n in row['nodes']if n!=FIXED});ids={n:i for i,n in enumerate(nodes)}
    output.mkdir(parents=True,exist_ok=False);edges=output/'edges.tsv'
    with edges.open('x')as f:
        f.write(f'{len(nodes)} {len(rows)}\n')
        for row in rows:
            a,b=row['nodes']
            if a==FIXED:a,b=b,a
            f.write(f'{ids[a]} {ids.get(b,-1)} {F(row["farads"])}\n')
    os.sched_setaffinity(0,{25});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1260
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=8,automatic_identical_retry=False))
    folder=Path(__file__).resolve().parent;cpp=folder.parents[1]/'tools/capacitance_energy/exact_sparse_ldl.cpp'
    files=[receipt,file,edges,binary,cpp,Path(__file__).resolve(),folder/'project_prototype_fixed_rail_C_v2.py'];pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins,node_count=len(nodes),capacitor_pairs=len(rows)))
    try:
        save(output/'status.json',dict(state='full_parent_exact_GMP_C_running',release_ready=False))
        report=output/'report.json'
        with lease(1,8,deadline):execute([binary,edges,report,'1200'],output/'native.log',deadline,8)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},result=json.loads(report.read_text()),models_modified=False,fixed_supplies_only=True,wire_R_inserted=False,native_simulation_allowed=False,release_ready=False))
        save(output/'status.json',dict(state='parent_GMP_C_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_certificate',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['source','binary','output']))
