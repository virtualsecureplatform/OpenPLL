#!/usr/bin/env python3
"""Collect the existing corner extractions with their original absolute budget.

Assess feedback, every capacitor and exact-zero reduction per corner, then
compare device/node statements and parent diagonals. Classify both decap and diode diagnostics, reusing the checked min feedback.
No native rerun/adoption.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from run_dco_qualification import ROOT,sha,save


def live(pid,marker):
    p=Path('/proc')/str(pid)
    try:
        return (p/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z' and marker in (p/'cmdline').read_bytes().decode()
    except (FileNotFoundError,ProcessLookupError):return False


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'poly_metal_full_capacitance_corners_002'
    out=base/'poly_metal_full_capacitance_corner_collection_002'
    owner=json.loads((source/'owner.json').read_text())
    deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    scripts={name:Path(__file__).with_name(filename) for name,filename in [
        ('feedback','audit_corner_feedback_v2.py'),('network','audit_corner_capacitance_network.py'),
        ('positive','remove_exact_zero_corner_capacitance.py'),('comparison','compare_full_capacitance_corners_v2.py')]}
    files=[Path(__file__).resolve(),source/'owner.json',source/'input_manifest.json',*scripts.values(),
        Path(__file__).with_name('audit_capacitance_corner_controls.py'),Path(__file__).with_name('audit_primitive_corner_exports.py')]
    pins={str(p):sha(p) for p in files}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def remaining():return deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_budget_s=max(0,remaining()),native_analog_jobs_added=0,release_qualified=False,**fields))
    def execute(label,command):
        assert remaining()>0
        for p,digest in pins.items():assert sha(Path(p))==digest,p
        with (out/f'{label}.log').open('x') as log:
            child=subprocess.Popen([sys.executable,*map(str,command)],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
            status('assessing_terminal_corner',stage=label,assessment_pid=child.pid)
            try:code=child.wait(timeout=max(0,remaining()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                status('timeout_inconclusive_during_assessment',stage=label)
                return False
        if code:
            status('assessment_nonpass',stage=label,exit_code=code)
            return False
        return True
    receipts=[]
    for corner in ['min','max']:
        extraction=source/corner
        while not (extraction/'native_completion.json').exists():
            if remaining()<=0:
                status('timeout_inconclusive_waiting_for_corner',corner=corner)
                return
            if not live(owner['runner_pid'],'queue_full_layout_capacitance_corners_v2.py'):
                status('queue_stopped_without_corner_receipt',corner=corner)
                return
            status('waiting_for_existing_corner',corner=corner,verified_queue_live=True)
            time.sleep(min(15,remaining()))
        native=json.loads((extraction/'native_completion.json').read_text())
        if not native['native_extraction_completed']:
            status('source_corner_terminal_nonpass',corner=corner)
            return
        target=out/corner
        target.mkdir()
        jobs=[('feedback',[scripts['feedback'],'--extraction',extraction,'--output',target/'feedback']),
            ('network',[scripts['network'],'--extraction',extraction,'--output',target/'network']),
            ('positive',[scripts['positive'],'--extraction',extraction,'--network-audit',target/'network','--output',target/'positive'])]
        if corner=='min':
            from check_compact_clock_tree import verify
            feedback=base/'poly_metal_min_corner_feedback_002/assessment.json'
            checked=verify(feedback)
            assert checked['full_corner_warning_classification_passed']
            assert checked['input_sha256'][str(extraction/'native_completion.json')]==sha(extraction/'native_completion.json')
            receipts.append(feedback)
            jobs=[row for row in jobs if row[0]!='feedback']
        for label,command in jobs:
            if not execute(corner+'_'+label,command):return
            receipts.append(target/label/'assessment.json')
    if not execute('corner_comparison',[scripts['comparison']]):return
    receipts.append(base/'poly_metal_full_capacitance_corner_comparison_002/assessment.json')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in receipts},
        both_corner_feedback_network_and_zero_cleanup_assessments_complete=True,
        normalized_device_and_parent_diagonal_comparison_complete=True,native_analog_jobs_added=0,
        native_extra_extractions_started=False,full_rc_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    status('terminal_corner_assessments_completed')
    print('Full-layout corner collection complete; model/material/distributed-RC and timing qualification remain open.',flush=True)


if __name__=='__main__':main()
