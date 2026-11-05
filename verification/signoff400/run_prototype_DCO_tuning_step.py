"""Observe a one-LSB tuning transient in the reviewed conventional-RC DCO."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge import execute
from assess_prototype_native_waveform import crossings


def step_deck(text):
    original='VCTRL128 DCO_THERM[128] 0 {VDD}'
    if text.splitlines().count(original)!=1 or text.splitlines().count('.tran 10.0p 80.0n 0 10.0p')!=1:raise ValueError('reviewed TT coarse-1 fine-128 80ns baseline required')
    if 'VRESET RESET_N 0 PULSE(0 {VDD} 5.0n 50p 50p 80.0n 160.0n)' not in text:raise ValueError('unchanged reset must remain released through capture')
    result=text.replace(original,'VCTRL128 DCO_THERM[128] 0 PWL(0 {VDD} 39.9n {VDD} 40.1n 0)')
    # Print the changing physical input as well as the oscillator output.
    if text.splitlines().count('.print tran v(PLLOUT)')!=1:raise ValueError('one original oscillator print required')
    return result.replace('.print tran v(PLLOUT)','.print tran v(PLLOUT) v(DCO_THERM[128])')


def table(text):
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text);rows=[]
    if len(declared)!=1:raise ValueError('one tuning-step native table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=4 or int(f[0])!=len(rows):raise ValueError('invalid tuning-step table')
        row=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in row) or rows and row[0]<=rows[-1][0]:raise ValueError('invalid tuning-step samples')
        rows.append(row)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or abs(rows[-1][0]-80e-9)>1e-15:raise ValueError('incomplete tuning-step capture')
    return rows


def metrics(rows):
    output=[(r[0],r[1]) for r in rows];rise,fall=crossings(output,.9);windows=[]
    for start,stop in ((20,35),(55,80)):
        edges=[t for t in rise if start*1e-9<=t<=stop*1e-9]
        if len(edges)<3:raise ValueError('insufficient settled pre/post tuning cycles')
        periods=[b-a for a,b in zip(edges,edges[1:])]
        windows.append(dict(window_ns=[start,stop],complete_cycles=len(periods),average_frequency_hz=(len(edges)-1)/(edges[-1]-edges[0]),period_interval_s=[min(periods),max(periods)]))
    control=crossings([(r[0],r[2]) for r in rows],.9)
    if control[0] or len(control[1])!=1 or abs(control[1][0]-40e-9)>1e-12:raise ValueError('physical tuning transition differs')
    return dict(windows=windows,output_rising_edges_s=rise,output_falling_edges_s=fall,
                physical_tuning_fall_s=control[1][0],instantaneous_periods_s=[b-a for a,b in zip(rise,rise[1:])])


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    base=ROOT/'build/signoff400/prototype_v3_TT_RC_KLU_profile_80ns_001'
    receipt=base/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256'])
    source=base/'native/dco_postlayout_tt_coarse_01_code_128.spice'
    reviewed=ROOT/'build/signoff400/prototype_v3_DCO_solver_waveform_comparison_001/alternative_waveform_review/assessment.json';a=json.loads(reviewed.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('reviewed baseline deck required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    deck=output/'tuning_step.cir';deck.write_text(step_deck(source.read_text()));init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
    pins={str(p):sha(p) for p in (receipt,source,reviewed,image,ng,deck,init,Path(__file__).resolve())};pins.update(r['input_sha256'])
    save(output/'input_manifest.json',dict(input_sha256=pins,corner='tt',coarse_code=1,initial_fine_code=128,final_fine_code=129,
         physical_transition_ns=[39.9,40.1],parent_loading_complete=False,diagnostic=True))
    save(output/'status.json',dict(state='native_DCO_tuning_step_running',release_ready=False))
    log=output/'native.log'
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],log,deadline,4)
    text=log.read_text()
    if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU selection required')
    result=metrics(table(text));detail=output/'observations.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (log,detail)},
         native_tuning_step_capture_complete=True,static_lookup_correlation_complete=False,phase_kick_uncertainty_bounded=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_DCO_tuning_step_complete',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
