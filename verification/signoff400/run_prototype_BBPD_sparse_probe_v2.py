"""Bounded partial-horizon diagnosis of native coupled BBPD; never qualifies full capture."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def observe(text,stop_ns):
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text);count=0;last=None;first=None
    if len(declared)!=1:raise ValueError('single native transient table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=9 or int(f[0])!=count:raise ValueError('malformed/truncated short-probe table')
        values=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in values) or (last is not None and values[0]<=last):raise ValueError('invalid waveform values/times')
        if first is None:first=values[0]
        last=values[0];count+=1
    if count!=int(declared[0]) or first!=0 or last is None or last<stop_ns*1e-9-1e-15:raise ValueError('short-probe observation horizon incomplete')
    return dict(samples=count,last_sample_s=last)


def run(output,stop_ns):
    reduced=True
    if stop_ns!=40:raise ValueError('declared SPARSE diagnostic horizon is 40 ns')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+300
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    source=ROOT/'build/signoff400/prototype_v3_BBPD_coupled_TT_pilot_001';manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    original=source/'phase_-1000ps/coupled.cir';text=original.read_text()
    reduction_paths=[]
    if reduced:
        folder=ROOT/'build/signoff400/prototype_v3_BBPD_fixed_rail_signal_model_001'
        rr=folder/'assessment.json';r=json.loads(rr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r.get('exact_retained_card_and_capacitor_reparse_pass') is not True:raise ValueError('exact signal reduction required')
        old=ROOT/'build/signoff400/prototype_v3_analog_capacitance_002/IntegerPLL_BBPD/capacitance.spice'
        if r['input_sha256'].get(str(old))!=m['input_sha256'].get(str(old)):raise ValueError('reduction of matching detector required')
        expected='.include \"'+str(old)+'\"'
        if text.count(expected)!=1 or 'VDD VDD 0 1.8' not in text:raise ValueError('fixed-rail fixture scope changed')
        text=text.replace(expected,'.include \"'+str(folder/'signal.spice')+'\"')
        reduction_paths=[rr,folder/'signal.spice',folder/'reduction.json']
    if text.count('.option klu method=gear')!=1:raise ValueError('expected solver controls changed')
    text=text.replace('.option klu method=gear','.option method=gear')
    text,n=re.subn(r'^\.tran 10p 90n 0 10p$',f'.tran 10p {stop_ns}n 0 10p',text,flags=re.M)
    if n!=1:raise ValueError('expected coupled transient controls changed')
    text='.option acct\n'+text
    # Keep a comment first: SPICE always treats the first line as its title.
    text='* Coupled BBPD bounded horizon resource probe\n'+text
    deck=output/'probe.cir';deck.write_text(text);init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47/install/bin/ngspice'
    binary_provenance=ROOT/'build/tools/ngspice47/binary_provenance.json'
    build=json.loads(binary_provenance.read_text())
    if '--disable-klu' not in build['commands'][0] or build['binary_sha256']!=sha(ng):raise ValueError('pinned KLU-disabled SPARSE build required')
    pins=dict(m['input_sha256']);pins.update({str(p):sha(p) for p in (manifest,original,deck,init,ng,binary_provenance,Path(__file__).resolve(),*reduction_paths)})
    save(output/'input_manifest.json',dict(input_sha256=pins,stop_ns=stop_ns,native_wall_limit_s=240,full_90ns_capture_required_for_parent_pilot=True,signal_only_fixed_rail_reduction_applied=reduced,linear_solver="SPARSE_1.3",added_shunt_capacitance_F_per_voltage_node=0))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    log=output/'native.log';started=time.monotonic()
    try:
        save(output/'status.json',dict(state='native_short_probe_running',stop_ns=stop_ns,release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],log,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+240),4)
        text=log.read_text()
        if 'Using KLU as Direct Linear Solver' in text:raise ValueError('unexpected KLU backend; SPARSE build required')
        observation=observe(text,stop_ns);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(log):sha(log)},native_short_horizon_completed=True,
            stop_ns=stop_ns,observations=observation,elapsed_wall_s=time.monotonic()-started,
            linear_solver="SPARSE_1.3",added_shunt_capacitance_F_per_voltage_node=0,numerical_convergence_qualified=False,full_transient_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='native_short_probe_complete',release_ready=False))
    except BaseException as exc:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--stop-ns',type=int,choices=(40,),required=True)
    a=p.parse_args();run(a.output.resolve(),a.stop_ns)
