#!/usr/bin/env python3
"""Reserve assessment time inside the existing deadline; never retry a native."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def terminate_identified(pid,expected,grace_s=10):
    observed=process(pid)
    if not observed['live']:return False
    assert observed['argv']==expected['argv'], 'native PID identity changed'
    assert os.getpgid(pid)==pid, 'native is not its process-group leader'
    os.killpg(pid,signal.SIGTERM)
    until=time.monotonic()+grace_s
    while process(pid)['live'] and time.monotonic()<until:time.sleep(.1)
    if process(pid)['live']:
        assert process(pid)['argv']==expected['argv']
        os.killpg(pid,signal.SIGKILL)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    point=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
    owner=json.loads((point/'owner.json').read_text());launch=json.loads((point/'launch.json').read_text())
    pid=launch['pid'];identity=process(pid)
    assert identity['live'] and identity['argv']==launch['command'] and identity['argv'][-1]==str(point/'point.cir')
    deadline=owner['deadline_uptime'];reserve_s=300;stop_at=deadline-reserve_s
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<stop_at
    if args.check_only:
        print(json.dumps(dict(check_only=True,native_changed=False,native_pid=pid,deadline_uptime=deadline,
            assessment_reserve_s=reserve_s,native_stop_uptime_if_still_running=stop_at)))
        return
    out=base/'DCO_bounded_reuse_assessment_deadline_guard_001';out.mkdir(exist_ok=False)
    pins={str(p):digest(p) for p in (Path(__file__).resolve(),point/'owner.json',point/'launch.json',point/'point.cir')}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        source_native_identity=identity,source_runner_pid=owner['runner_pid'],deadline_uptime=deadline,
        assessment_reserve_s=reserve_s,native_stop_uptime_if_still_running=stop_at,
        budget_restarted=False,native_retry_allowed=False,input_sha256=pins))
    interrupted=False
    while True:
        now=time.clock_gettime(time.CLOCK_BOOTTIME);current=process(pid)
        if not current['live']:break
        assert current['argv']==identity['argv'], 'PID reused; refuse to signal another process'
        if now>=stop_at:
            for p,sha in pins.items():assert digest(Path(p))==sha,p
            save(out/'stop_decision.json',dict(reason='Reserve assessment time inside the original12h experiment budget',
                observed_utc=datetime.now(timezone.utc).isoformat(),uptime=now,deadline_uptime=deadline,
                native_identity=current,physical_failure_inferred=False,native_timeout_assessment_inconclusive=True))
            interrupted=terminate_identified(pid,identity)
            break
        save(out/'status.json',dict(state='waiting_for_native_completion_or_assessment_reserve',source_native_live=True,
            deadline_uptime=deadline,native_stop_uptime_if_still_running=stop_at,release_qualified=False))
        time.sleep(min(30,max(.01,stop_at-now)))
    receipt=point/'assessment.json';failure=point/'runner_failure.json'
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        if receipt.exists() or (not process(owner['runner_pid'])['live'] and failure.exists()):break
        if not process(owner['runner_pid'])['live']:break
        save(out/'status.json',dict(state='waiting_for_terminal_source_receipt',controlled_budget_stop=interrupted,
            source_native_live=process(pid)['live'],deadline_uptime=deadline,release_qualified=False))
        time.sleep(min(2,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    observed=time.clock_gettime(time.CLOCK_BOOTTIME)
    save(out/'assessment.json',dict(controlled_budget_stop=interrupted,source_native_live=process(pid)['live'],
        source_runner_live=process(owner['runner_pid'])['live'],source_receipt=str(receipt) if receipt.exists() else None,
        source_receipt_sha256=digest(receipt) if receipt.exists() else None,
        source_runner_failure=str(failure) if failure.exists() else None,
        terminal_receipt_observed_within_original_deadline=receipt.exists() and observed<=deadline,
        assessed_uptime=observed,deadline_uptime=deadline,budget_restarted=False,native_retried=False,
        physical_failure_inferred=False,release_qualified=False,adopted=False))
    save(out/'status.json',dict(state='deadline_guard_finished',controlled_budget_stop=interrupted,
        source_receipt_present=receipt.exists(),release_qualified=False))


if __name__=='__main__':main()
