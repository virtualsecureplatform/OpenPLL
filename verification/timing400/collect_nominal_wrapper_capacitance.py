#!/usr/bin/env python3
"""Assess the live nominal wrapper export without restarting extraction.

Retain the original CAD deadline for waiting, warning audit, network checks,
exact-zero cleanup and comparison to the existing nominal/min/max evidence.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from collect_full_capacitance_corners_v2 import live
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'poly_metal_full_nominal_wrapper_001'
    out=base/'nominal_wrapper_capacitance_collection_001'
    owner=json.loads((source/'owner.json').read_text());deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    names={'feedback':'audit_corner_feedback_v2.py','network':'audit_corner_capacitance_network.py',
        'positive':'remove_exact_zero_corner_capacitance.py','comparison':'compare_nominal_wrapper_capacitance.py'}
    scripts={k:Path(__file__).with_name(v) for k,v in names.items()}
    paths=[Path(__file__).resolve(),source/'owner.json',source/'input_manifest.json',*scripts.values(),
        Path(__file__).with_name('compare_full_capacitance_corners_v2.py')]
    pins={str(p):sha(p) for p in paths};out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def remaining():return deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    def status(state,**kw):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
        remaining_budget_s=max(0,remaining()),native_analog_jobs_added=0,release_qualified=False,**kw))
    while not (source/'native_completion.json').exists():
        if remaining()<=0:status('timeout_inconclusive_waiting_for_existing_extraction');return
        native=json.loads((source/'status.json').read_text())
        runner_live=live(owner['runner_pid'],'run_full_layout_nominal_wrapper_capacitance.py')
        native_live=live(native.get('native_pid',-1),'magicdnull')
        if not runner_live and not native_live:status('source_stopped_without_completion');return
        status('waiting_for_existing_nominal_wrapper',verified_runner_live=runner_live,verified_native_live=native_live)
        time.sleep(min(15,remaining()))
    native=json.loads((source/'native_completion.json').read_text())
    if not native['native_extraction_completed']:status('source_native_nonpass');return
    commands=[('feedback',[scripts['feedback'],'--extraction',source,'--output',out/'feedback']),
        ('network',[scripts['network'],'--extraction',source,'--output',out/'network']),
        ('positive',[scripts['positive'],'--extraction',source,'--network-audit',out/'network','--output',out/'positive']),
        ('comparison',[scripts['comparison']])]
    receipts=[]
    for label,command in commands:
        if remaining()<=0:status('timeout_inconclusive_before_assessment',stage=label);return
        for p,d in pins.items():assert sha(Path(p))==d,p
        with (out/f'{label}.log').open('x') as log:
            child=subprocess.Popen([sys.executable,*map(str,command)],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
            status('assessing_nominal_wrapper',stage=label,assessment_pid=child.pid)
            try:code=child.wait(timeout=max(0,remaining()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                status('timeout_inconclusive_during_assessment',stage=label);return
        if code:status('assessment_nonpass',stage=label,exit_code=code);return
        receipts.append((base/'nominal_wrapper_capacitance_comparison_001' if label=='comparison' else out/label)/'assessment.json')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in receipts},
        warning_network_zero_cleanup_and_comparison_assessments_terminal=True,
        source_native_extractions_restarted=False,native_analog_jobs_added=0,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    status('nominal_wrapper_assessments_terminal')
    print('Nominal wrapper assessment terminal; electrical/model/RC qualification remains separate.')


if __name__=='__main__':main()
