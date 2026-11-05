#!/usr/bin/env python3
"""Correct duration reset stimulus and retain the original total check deadline.

Change only reset pulse width/period so reset stays released throughout the
existing160ns experiment. No oscillator/model/solver input changes, identical
native retry, budget reset, or automatic PVT expansion. Retain every declared
window, including insufficient-edge or sustained-oscillation failures.
"""
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from audit_dco_settling_windows import independent_edges
from benchmark_dco_linear_solver_v2 import waveform
from run_dco_duration_probe_v3 import decimal_measure
from guarded_native_admission import scan
from characterize_compact_propagation import XYCE
from run_dco_qualification import ROOT,sha,save,measure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',required=True,type=Path)
    parser.add_argument('--claim',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();original=args.original.resolve();claim=args.claim.resolve()
    plan_path=original/'plan.json';plan=json.loads(plan_path.read_text());owner=json.loads(claim.read_text())
    deadline=owner['absolute_deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    assert plan['stop_ns']==160 and plan['pvt']==dict(corner='tt',temperature_c=27,supply_v=1.8)
    old=original/'duration.spice';text=old.read_text()
    before=re.search(r'^VRESET .*$',text,re.M)[0];assert '80.0n 160.0n)' in before
    after=before.replace('80.0n 160.0n)','160.0n 320.0n)')
    changed=text.replace(before,after);assert changed!=text and len(re.findall(r'^VRESET ',changed,re.M))==1
    assert '.tran 10.0p 160n' in changed
    retired=ROOT/'build/timing400/release_001/scheduling_handoff_002/assessment.json'
    assert json.loads(retired.read_text())['retired_dco_dispatcher']==3785484
    for pid in [3785484,3867630]:
        p=Path('/proc')/str(pid)
        assert not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z'
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_claim=str(claim),absolute_deadline_uptime=deadline,total_budget_restarted=False,
        includes_admission_and_assessment=True,automatic_identical_retry=False))
    circuit=out/'duration.spice';circuit.write_text(changed)
    files=[Path(__file__).resolve(),claim,plan_path,old,circuit,retired,XYCE,
        Path(__file__).with_name('run_dco_duration_probe_v3.py'),Path(__file__).with_name('audit_dco_settling_windows.py'),
        Path(__file__).with_name('benchmark_dco_linear_solver_v2.py'),ROOT/'scripts/dco_calibration.py']
    pins={**plan['input_sha256'],**{str(p):sha(p) for p in files}}
    for p,digest in pins.items():assert sha(p)==digest,p
    save(out/'input_manifest.json',dict(input_sha256=pins,original_reset=before,corrected_reset=after,
        only_reset_width_and_period_changed=True,original_declared_windows_ns=plan['predeclared_windows_ns'],
        original_absolute_deadline_uptime=deadline,scope=__doc__))
    def remaining():
        left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:raise TimeoutError('original12h deadline exhausted')
        return left
    def status(state,**fields):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
        remaining_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,**fields))
    child=None
    try:
        with (out/'run.log').open('x') as log:
            while child is None:
                remaining()
                with (ROOT/'build/timing400/guarded_native_admission.lock').open('a') as lock:
                    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError:pass
                    else:
                        native=scan()
                        if len(native)<4:
                            command=[str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'duration'),str(circuit)]
                            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
                            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                            until=time.monotonic()+2
                            while child.poll() is None and not any(r['pid']==child.pid for r in scan()):
                                assert time.monotonic()<until
                                time.sleep(.01)
                            after_native=scan();assert len(after_native)<=4
                            save(out/'launch.json',dict(pid=child.pid,command=command,native_before=native,native_after=after_native,
                                dispatchers_retired=True,original_absolute_deadline_uptime=deadline))
                if child is None:status('waiting_for_native_capacity');time.sleep(min(30,remaining()))
            status('native_running',native_pid=child.pid)
            code=child.wait(timeout=remaining())
        save(out/'native_completion.json',dict(exit_code=code,original_absolute_deadline_uptime=deadline,release_qualified=False))
        if code:status('native_nonpass',exit_code=code);return
        status('assessing_terminal_native_waveform')
        wave=out/'duration.prn';times,values=waveform(wave);assert times[-1]>=160e-9-1e-15
        edges=independent_edges(wave);rows=[]
        for start,stop in plan['predeclared_windows_ns']:
            remaining();row=dict(start_ns=start,stop_ns=stop)
            selected=[t for t in edges if Decimal(start)*Decimal('1e-9')<=t<=Decimal(stop)*Decimal('1e-9')]
            try:
                metric=measure(wave,start,stop,1.8,min_periods=3);freq,drift=decimal_measure(edges,start,stop)
                assert abs(float(freq)-metric['mhz'])<1e-8 and abs(float(drift)-metric['half_window_difference_mhz'])<1e-8
                period=(selected[-1]-selected[0])/Decimal(len(selected)-1)
                sustained=(selected[0]-Decimal(start)*Decimal('1e-9')<=2*period and
                           Decimal(stop)*Decimal('1e-9')-selected[-1]<=2*period and
                           max(b-a for a,b in zip(selected,selected[1:]))<=2*period)
                row.update(**metric,independent_decimal_frequency_mhz=str(freq),
                    independent_decimal_half_window_difference_mhz=str(drift),sustained_oscillation_observed=bool(sustained),
                    state='measured' if sustained else 'insufficient_sustained_coverage')
                if stop<=80:
                    reference=measure(Path(plan['reference_waveform']),start,stop,1.8,min_periods=3)
                    row.update(reference_80ns_run=reference,duration_run_minus_reference_mhz=metric['mhz']-reference['mhz'])
            except (ValueError,AssertionError,IndexError) as error:
                row.update(state='window_unmeasurable',reason=repr(error),rising_edges=len(selected),sustained_oscillation_observed=False)
            rows.append(row)
        for p,digest in pins.items():assert sha(p)==digest,p
        remaining()
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
            records=rows,all_predeclared_windows_retained=True,native_waveform_terminal=True,reset_remains_released_until_stop=True,
            pvt=plan['pvt'],code=plan['code'],coarse=plan['coarse'],stop_ns=160,
            all_windows_have_sustained_oscillation=all(r['sustained_oscillation_observed'] for r in rows),
            measurement_window_adopted=False,calibration_model_qualified=False,release_qualified=False,scope=__doc__))
        status('terminal_assessment',retained_windows=len(rows))
    except (TimeoutError,subprocess.TimeoutExpired):
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        status('timeout_inconclusive')

if __name__=='__main__':main()
