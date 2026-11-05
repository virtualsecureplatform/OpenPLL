#!/usr/bin/env python3
"""Retire stale dispatchers while preserving every currently running native job.

Do not alter pinned inputs, terminate native children, reset budgets, or rerun
completed cases. The old receiver's remaining unlaunched cases use superseded
parent routing; broad DCO expansion must wait for a qualified measurement
profile. Existing native wrappers retain their output files and watchdogs.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import time
from guarded_native_admission import scan,process_stat
from run_dco_qualification import ROOT,sha,save


def identity(pid,script):
    p=Path('/proc')/str(pid)
    argv=(p/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    assert str(ROOT/'verification/timing400'/script) in argv,(pid,argv)
    stat=process_stat(pid);assert stat[0] not in ('T','t','Z')
    return dict(pid=pid,start_ticks=int(stat[19]),argv=argv,state=stat[0])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();assert not out.exists()
    base=ROOT/'build/timing400/release_001'
    lock_path=ROOT/'build/timing400/guarded_native_admission.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        capture=base/'assembled_receiver_capture_tt27_001'
        status=json.loads((capture/'run_001/status.json').read_text())
        assert status['state']=='waiting_for_guarded_native_capacity' and status['case_index']==1
        assert not (capture/'run_001/point_1/launch.json').exists()
        assert (capture/'run_001/point_0/assessment.json').exists()
        collector=identity(3867630,'check_assembled_receiver_capture.py')
        dispatcher=identity(3785484,'run_dco_qualification.py')
        before=scan();assert {r['pid'] for r in before}=={3848655,3866065,3869348,3870121}
        native_starts={r['pid']:int(process_stat(r['pid'])[19]) for r in before}
        dco_state=json.loads((base/'dco/status.json').read_text())
        assert not any(r.get('state')=='waiting_for_native_slot' for r in dco_state['stages'].values())
        # Pin completed failure evidence motivating the handoff, not live waves.
        evidence=[base/'dco_window_sensitivity_001/assessment.json',
            base/'dco_tt250_window_review_001/assessment.json',
            base/'parent_dco_antenna_route_dedup_001/assessment.json',
            capture/'plan.json',capture/'run_001/owner.json',capture/'run_001/point_0/assessment.json']
        assert all(p.exists() for p in evidence)
        out.mkdir(parents=True)
        save(out/'intent.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),
            dispatchers=[collector,dispatcher],native_before=before,native_start_ticks=native_starts,
            reason='Receiver routing superseded; baseline80ns fails settled-measurement prerequisite. Retire dispatch only; preserve current native jobs.',
            release_qualified=False))
        for item in [collector,dispatcher]:
            fd=os.pidfd_open(item['pid'])
            try:
                assert int(process_stat(item['pid'])[19])==item['start_ticks']
                signal.pidfd_send_signal(fd,signal.SIGTERM)
            finally:os.close(fd)
        until=time.monotonic()+5
        for item in [collector,dispatcher]:
            while (Path('/proc')/str(item['pid'])).exists():
                if process_stat(item['pid'])[0]=='Z':break
                assert time.monotonic()<until,'dispatcher did not terminate'
                time.sleep(.02)
        after=scan();assert {r['pid'] for r in after}==set(native_starts)
        for pid,start in native_starts.items():
            state=process_stat(pid);assert int(state[19])==start and state[0] not in ('T','t','Z')
        old_budget=json.loads((capture/'run_001/owner.json').read_text())
        save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),*evidence]},
            artifacts={str(out/'intent.json'):sha(out/'intent.json')},dispatchers_retired=[collector,dispatcher],
            native_before=before,native_after=after,native_jobs_preserved=4,native_children_paused=False,
            completed_receiver_cases_retained=1,unlaunched_receiver_cases_superseded=3,
            replacement_receiver_original_deadline_uptime=old_budget['deadline_uptime'],
            completed_dco_artifacts_retained=True,tt100_native_wrappers_continue=True,
            broad_pvt_dispatch_deferred_until_measurement_profile_qualified=True,
            all_15_nominal_pvt_requirements_unchanged=True,no_identical_retry=True,
            release_qualified=False,scope=__doc__))
        save(capture/'dispatch_superseded.json',dict(assessment=str(out/'assessment.json'),
            pending_cases_superseded=[1,2,3],completed_cases_retained=[0],
            original_deadline_uptime=old_budget['deadline_uptime'],budget_restarted=False,release_qualified=False))
        save(base/'dco/dispatch_retired.json',dict(assessment=str(out/'assessment.json'),
            native_children_continue=True,range_results_may_be_collected_from_completed_csv=True,
            calibrated_profile_required_before_more_pvt_dispatch=True,release_qualified=False))
    print('Retired two obsolete dispatchers; all four native jobs continue unchanged. Original receiver deadline retained.')

if __name__=='__main__':main()
