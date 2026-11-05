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
    if not 0<abstol<=1e-9:raise ValueError('current tolerance exceeds prototype profile')
    output.mkdir(parents=True,exist_ok=False)
    source=reference/'native/dco_postlayout_tt_coarse_01_code_128.spice';lines=[]
    for line in source.read_text().splitlines():
        if line.startswith('.tran'):line=re.sub(r'^(\.tran\s+\S+\s+)\S+',r'\g<1>30n',line)
        if line.startswith('.option'):line=re.sub(r'\babstol=\S+',f'abstol={abstol:.17g}',line)
        lines.append(line)
    lines.insert(1,'.option klu');deck=output/'probe.cir';deck.write_text('\n'.join(lines)+'\n')
    init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins={str(p):sha(p) for p in (source,deck,init,image,ng,Path(__file__).resolve())}
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+240
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    started=time.monotonic()
    try:
        save(output/'status.json',dict(state='bounded_KLU_resource_probe_running',abstol_A=abstol,release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],output/'native.log',deadline,4)
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
