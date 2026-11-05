#!/usr/bin/env python3
"""Serialize full-layout C corners after the existing large FOM CAD extraction.

Use the original layout deadline including this wait and later assessments.
No reference retry, fabrication change, analog engine or model adoption.
"""
from datetime import datetime, timezone
import fcntl
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
    except (FileNotFoundError,ProcessLookupError):
        return False


def main():
    base=ROOT/'build/timing400/release_001'
    out=base/'poly_metal_full_capacitance_corners_001'
    source=base/'parent_filled_poly_metal_capacitance_view_003'
    waiting=base/'fom_bulk_surface_reference_extract_004'
    waiting_owner=json.loads((waiting/'owner.json').read_text())
    owner_path=source/'owner.json'
    owner=json.loads(owner_path.read_text())
    deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    worker=Path(__file__).with_name('run_full_layout_capacitance_corner.py')
    paths=[Path(__file__).resolve(),worker,owner_path,source/'assessment.json',
        waiting/'owner.json',waiting/'input_manifest.json',
        base/'capacitance_corner_control_audit_001/assessment.json',base/'primitive_corner_export_audit_001/assessment.json']
    pins={str(p):sha(p) for p in paths}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,
        includes_wait_execution_and_later_assessment=True,automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_budget_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),
            native_analog_jobs_added=0,release_qualified=False,**fields))
    while not (waiting/'native_completion.json').exists():
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:
            status('timeout_inconclusive_queued_for_cad_memory')
            return
        current=json.loads((waiting/'status.json').read_text())
        native_live=live(current.get('native_pid',-1),'magicdnull')
        runner_live=live(waiting_owner['runner_pid'],'run_fom_bulk_surface_reference.py')
        if not native_live and not runner_live:
            # The checks are independent; resource release after a stopped
            # reference is sufficient. Never retry the stopped reference.
            status('reference_stopped_without_receipt_resources_released')
            break
        status('waiting_for_existing_large_cad_extraction',verified_native_live=native_live,
            verified_runner_live=runner_live,source_status=current)
        time.sleep(min(15,remaining))
    with (ROOT/'build/timing400/full_capacitance_cad.lock').open('a') as lock:
        while True:
            if deadline<=time.clock_gettime(time.CLOCK_BOOTTIME):
                status('timeout_inconclusive_waiting_for_cad_lock')
                return
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                status('waiting_for_cad_lock')
                time.sleep(15)
        for corner in ['min','max']:
            for p,digest in pins.items():
                assert sha(Path(p))==digest,p
            remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining<=0:
                status('timeout_inconclusive_before_corner',corner=corner)
                return
            target=out/corner
            command=[sys.executable,str(worker),'--view',str(source),'--output',str(target),'--corner',corner]
            with (out/f'{corner}.log').open('x') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
                status('running_full_layout_corner',corner=corner,runner_pid=child.pid)
                try:
                    code=child.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL)
                        child.wait()
                    status('timeout_inconclusive_during_corner',corner=corner)
                    return
            if code or not (target/'native_completion.json').exists():
                status('corner_native_or_preparation_nonpass',corner=corner,exit_code=code)
                return
            result=json.loads((target/'native_completion.json').read_text())
            if not result['native_extraction_completed']:
                status('corner_native_nonpass',corner=corner)
                return
    save(out/'native_completion.json',dict(input_sha256=pins,
        artifacts={str(out/c/'native_completion.json'):sha(out/c/'native_completion.json') for c in ['min','max']},
        both_full_layout_corner_extractions_completed=True,assessments_still_required=True,
        original_deadline_uptime=deadline,native_analog_jobs_added=0,full_rc_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    status('raw_full_layout_corners_terminal_assessments_pending')
    print('Both full-layout corner extractions terminal; raw-network and geometry assessments still required under original deadline.')


if __name__=='__main__':
    main()
