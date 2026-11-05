#!/usr/bin/env python3
"""Retire obsolete dispatch/capture work; preserve the two live TT100 endpoints.

The 160ns duration probes retained an80ns reset pulse. Their correction must
precede more PVT work. The active receiver probe uses superseded parent RC;
retain its partial evidence and first completed case without a silicon-failure
claim. Preserve every original absolute check deadline for replacements.
"""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import time
from guarded_native_admission import scan,process_stat
from run_dco_qualification import ROOT,sha,save

base=ROOT/'build/timing400/release_001';out=base/'scheduling_handoff_002'
assert not out.exists()
with (ROOT/'build/timing400/guarded_native_admission.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=json.loads((base/'assembled_receiver_capture_tt27_001/run_001/status.json').read_text())
    assert state['state']=='native_running' and state['case_index']==1 and state['native_pid']==3882506
    targets=[]
    for pid,token in [(3785484,'run_dco_qualification.py'),(3867630,'check_assembled_receiver_capture.py'),(3882506,'assembled_receiver_capture_tt27_001/phase-200_edge200/capture.cir')]:
        argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode()
        assert token in argv,(pid,argv)
        targets.append(dict(pid=pid,start_ticks=int(process_stat(pid)[19]),argv=argv.rstrip('\0').split('\0')))
    before=scan();assert {r['pid'] for r in before}=={3869348,3870121,3882506}
    starts={r['pid']:int(process_stat(r['pid'])[19]) for r in before if r['pid']!=3882506}
    evidence=[base/'dco_duration_reset_stimulus_failure_001/assessment.json',base/'parent_dco_antenna_route_dedup_001/assessment.json',
        base/'assembled_receiver_capture_tt27_001/run_001/point_0/assessment.json',base/'assembled_receiver_capture_tt27_001/run_001/owner.json']
    assert all(p.exists() for p in evidence)
    out.mkdir()
    save(out/'intent.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),targets=targets,native_before=before,
        reason='Correct invalid reset stimulus before broad expansion; cancel obsolete RC capture without treating it as a silicon failure.',release_qualified=False))
    for item in targets:
        fd=os.pidfd_open(item['pid'])
        try:
            assert int(process_stat(item['pid'])[19])==item['start_ticks']
            signal.pidfd_send_signal(fd,signal.SIGTERM)
        finally:os.close(fd)
    until=time.monotonic()+5
    for item in targets:
        while (Path('/proc')/str(item['pid'])).exists() and process_stat(item['pid'])[0]!='Z':
            assert time.monotonic()<until
            time.sleep(.02)
    after=scan();assert {r['pid'] for r in after}==set(starts)
    for pid,start in starts.items():assert int(process_stat(pid)[19])==start and process_stat(pid)[0] not in ['T','t','Z']
    capture=base/'assembled_receiver_capture_tt27_001'
    capdeadline=json.loads((capture/'run_001/owner.json').read_text())['deadline_uptime']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),*evidence]},
        artifacts={str(out/'intent.json'):sha(out/'intent.json')},native_before=before,native_after=after,
        preserved_tt100_native_pids=sorted(starts),retired_dco_dispatcher=3785484,retired_receiver_dispatcher=3867630,
        superseded_active_receiver_native=3882506,completed_receiver_case_retained=0,partial_case_retained=1,
        unlaunched_receiver_cases_superseded=[2,3],replacement_receiver_original_deadline_uptime=capdeadline,
        all_required_nominal15pvt_checks_remain_required=True,release_qualified=False,scope=__doc__))
    save(capture/'dispatch_superseded.json',dict(assessment=str(out/'assessment.json'),completed_cases_retained=[0],
        partial_cases_retained=[1],unlaunched_cases=[2,3],original_deadline_uptime=capdeadline,budget_restarted=False,release_qualified=False))
    save(base/'dco/dispatch_retired.json',dict(assessment=str(out/'assessment.json'),native_children_continue=True,
        range_results_may_be_collected_from_completed_csv=True,calibrated_profile_required_before_more_pvt_dispatch=True,release_qualified=False))
print('Retired obsolete dispatch and receiver work; both TT100 native jobs continue. Replacement check deadlines retained.')
