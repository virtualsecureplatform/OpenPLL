#!/usr/bin/env python3
"""Assess the already-running FOM bulk-surface reference extraction without restarting it.

Waiting and assessments share the original layout deadline. Preserve terminal
nonpasses and partial outputs; no native analog process or model adoption.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from run_dco_qualification import ROOT, sha, save


def live(pid, marker):
    proc = Path('/proc')/str(pid)
    try:
        state = (proc/'stat').read_text().rsplit(')',1)[1].split()[0]
        argv = (proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        return state!='Z' and marker in argv
    except (FileNotFoundError,ProcessLookupError):
        return False


def main():
    base = ROOT/'build/timing400/release_001'
    source = base/'fom_bulk_surface_reference_extract_004'
    out = base/'fom_bulk_surface_reference_collection_001'
    owner = json.loads((source/'owner.json').read_text())
    deadline = owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    inventory = base/'flat_decap_warning_gate_inventory_001/assessment.json'
    assert inventory.exists()
    feedback_script = Path(__file__).with_name('audit_flat_decap_feedback.py')
    network_script = Path(__file__).with_name('audit_parent_capacitance_network.py')
    comparison_script = Path(__file__).with_name('compare_fom_bulk_surface_reference.py')
    jobs = [('decap_feedback',[feedback_script,'--extraction',source,'--output',base/'fom_bulk_surface_decap_feedback_001']),
        ('full_capacitance_network',[network_script,'--extraction',source,'--output',base/'fom_bulk_surface_reference_network_audit_001']),
        ('bulk_surface_sensitivity',[comparison_script])]
    files = [Path(__file__).resolve(),source/'owner.json',source/'input_manifest.json',inventory,
        feedback_script,network_script,comparison_script]
    pins = {str(p):sha(p) for p in files}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'),deadline_uptime=deadline,total_budget_restarted=False,
        automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_budget_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,**fields))
    while not (source/'native_completion.json').exists():
        left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:
            status('timeout_inconclusive_waiting_for_source')
            return
        current = json.loads((source/'status.json').read_text())
        native_live = live(current.get('native_pid',-1),'magicdnull')
        runner_live = live(owner['runner_pid'],'run_fom_bulk_surface_reference.py')
        if not native_live and not runner_live:
            status('source_stopped_without_terminal_receipt',source_status=current)
            return
        status('waiting_for_existing_extraction',source_status=current,verified_native_live=native_live,
            verified_runner_live=runner_live)
        time.sleep(min(15,left))
    receipt = json.loads((source/'native_completion.json').read_text())
    if not receipt['native_extraction_completed']:
        status('source_terminal_nonpass')
        return
    for label,command in jobs:
        for p,digest in pins.items():
            assert sha(p)==digest,p
        left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:
            status('timeout_inconclusive_before_assessment',stage=label)
            return
        with (out/f'{label}.log').open('x') as log:
            child = subprocess.Popen([sys.executable,*map(str,command)],stdout=log,stderr=subprocess.STDOUT,
                cwd=ROOT,start_new_session=True)
            status('assessing_terminal_source',stage=label,assessment_pid=child.pid)
            try:
                code = child.wait(timeout=left)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait()
                status('timeout_inconclusive_during_assessment',stage=label)
                return
        if code:
            status('assessment_nonpass',stage=label,exit_code=code)
            return
    results = [base/'fom_bulk_surface_decap_feedback_001/assessment.json',
        base/'fom_bulk_surface_reference_network_audit_001/assessment.json',
        base/'fom_bulk_surface_reference_comparison_001/assessment.json']
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in results},source_collected=True,
        full_feedback_and_network_assessments_completed=True,native_analog_jobs_added=0,
        source_native_restarted=False,counterfactual_reference_only=True,
        actual_fom_material_equivalence_qualified=False,quantitative_enclosure_qualified=False,model_adopted=False,release_qualified=False,scope=__doc__))
    status('terminal_raw_network_assessments_completed')
    print('Counterfactual FOM bulk-surface source collected and assessed; manufacturing equivalence and enclosure remain unqualified.',flush=True)


if __name__=='__main__':
    main()
