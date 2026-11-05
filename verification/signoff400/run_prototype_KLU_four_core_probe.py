"""Bounded stock-KLU transient probe with explicit current tolerance; never release evidence."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def run(reference,output,abstol):
    if abstol!=1e-9:raise ValueError("matched profile ABSTOL required for thread benchmark")
    if not 0<abstol<=1e-9:raise ValueError('current tolerance exceeds prototype profile')
    output.mkdir(parents=True,exist_ok=False)
    source=reference/'native/dco_postlayout_tt_coarse_01_code_128.spice';lines=[]
    for line in source.read_text().splitlines():
        if line.startswith('.tran'):line=re.sub(r'^(\.tran\s+\S+\s+)\S+',r'\g<1>30n',line)
        if line.startswith('.option'):
            line=re.sub(r'\babstol=\S+',f'abstol={abstol:.17g}',line)
            line=re.sub(r'\bnum_threads=\S+','num_threads=4',line)
        lines.append(line)
    lines.insert(1,'.option klu');deck=output/'probe.cir';deck.write_text('\n'.join(lines)+'\n')
    init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    baseline=ROOT/'build/signoff400/prototype_v3_RC_KLU_profile_tolerance_probe_001/probe.cir'
    if deck.read_text().replace('num_threads=4','num_threads=1')!=baseline.read_text():raise ValueError('thread benchmark changes non-thread native deck records')
    pins={str(p):sha(p) for p in (source,deck,init,image,ng,baseline,Path(__file__).resolve())}
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+240
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=4,memory_GiB=4,automatic_identical_retry=False))
    started=time.monotonic()
    try:
        save(output/'status.json',dict(state='bounded_KLU_resource_probe_running',abstol_A=abstol,release_ready=False))
        with lease(4,4,deadline):
            allowed=sorted(os.sched_getaffinity(0));cores={};chosen=[]
            for cpu in allowed:
                base=Path('/sys/devices/system/cpu')/('cpu'+str(cpu))/'topology'
                key=((base/'physical_package_id').read_text().strip(),(base/'core_id').read_text().strip())
                if key not in cores:cores[key]=cpu;chosen.append(cpu)
                if len(chosen)==4:break
            if len(chosen)!=4:raise ValueError('four distinct physical cores required')
            os.sched_setaffinity(0,set(chosen))
            save(output/'physical_cores.json',dict(logical_cpu_ids=chosen,physical_core_keys=[list(k) for k in cores],threads=4,shared_cpu_lease=4,SMT_used=False))
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],output/'native.log',deadline,4)
        verify(pins);text=(output/'native.log').read_text()
        if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU not selected')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'native.log'):sha(output/'native.log')},elapsed_s=time.monotonic()-started,
             abstol_A=abstol,simulated_duration_ns=30,baseline_80ns_requirement_met=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='resource_probe_complete_review_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--abstol',type=float,required=True)
    a=p.parse_args();run(a.reference.resolve(),a.output.resolve(),a.abstol)
