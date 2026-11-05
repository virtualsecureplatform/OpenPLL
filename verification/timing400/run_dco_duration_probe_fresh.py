#!/usr/bin/env python3
"""Fresh guarded DCO duration check with one total12h budget and no retry.

Retains every predeclared window. No window, frequency model or release candidate
is adopted. Requires the preceding multi-point receiver owner to be terminal.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time

from audit_dco_settling_windows import independent_edges
from benchmark_dco_linear_solver_v2 import waveform
from characterize_compact_propagation import ROOT,XYCE
from guarded_native_admission import AdmissionDeferred,launch
from run_dco_duration_probe_v3 import decimal_measure
from run_dco_qualification import measure,sha,save


def main():
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical-workspace',required=True,type=Path)
    parser.add_argument('--plan',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--after-terminal',required=True,type=Path)
    parser.add_argument('--controller-pid',required=True,type=int)
    args=parser.parse_args()
    assert ROOT==args.canonical_workspace.resolve()
    path,out,preceding=args.plan.resolve(),args.output.resolve(),args.after_terminal.resolve()
    plan=json.loads(path.read_text());prior=json.loads(preceding.read_text())
    assert plan['pvt']==dict(corner='tt',temperature_c=27,supply_v=1.8)
    assert plan['code']==247 and plan['coarse']==1 and plan['stop_ns']==160 and plan['solver']=='KLU'
    assert len(prior['results'])==4
    previous_owner=preceding.parent/'owner.json'
    owner=json.loads(previous_owner.read_text())
    assert not (Path('/proc')/str(owner['runner_pid'])).exists(),'preceding external owner is still live'
    pins={**plan['input_sha256'],**prior['input_sha256'],str(path):sha(path),
          str(preceding):sha(preceding),str(previous_owner):sha(previous_owner)}
    for i,record in enumerate(prior['results']):
        for name,key in [('capture.prn','waveform_sha256'),('run.log','native_log_sha256')]:
            item=preceding.parent/f'point_{i}'/name
            assert sha(item)==record[key]
            pins[str(item)]=sha(item)
    for name in ('run_dco_duration_probe_fresh.py','run_dco_duration_probe_v3.py',
                 'guarded_native_admission.py','audit_dco_settling_windows.py',
                 'benchmark_dco_linear_solver_v2.py','characterize_compact_propagation.py',
                 'run_dco_qualification.py'):
        item=Path(__file__).with_name(name).resolve();pins[str(item)]=sha(item)
    for name,digest in pins.items():assert sha(name)==digest,name
    out.mkdir(parents=True,exist_ok=False)
    with (path.parent/'native_run_fresh.json').open('x') as stream:
        json.dump(dict(runner_pid=os.getpid(),output=str(out),started_utc=datetime.now(timezone.utc).isoformat(),
            absolute_deadline_uptime=deadline,automatic_identical_retry=False),stream,indent=2)

    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            total_budget_s=43200,absolute_deadline_uptime=deadline,release_qualified=False,**fields))

    def remaining():
        left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:
            status('timeout_inconclusive');raise TimeoutError('total12h budget exhausted')
        return left

    command=[str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'duration'),str(path.parent/'duration.spice')]
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    with (out/'run.log').open('x') as log:
        while True:
            remaining()
            try:
                child=launch(command,env,log,args.controller_pid,out/'guarded_admission.json');break
            except AdmissionDeferred as error:
                status('waiting_for_guarded_native_capacity',reason=str(error))
                time.sleep(min(30,remaining()))
        save(out/'launch.json',dict(pid=child.pid,command=command,input_sha256=pins))
        status('native_running',native_pid=child.pid)
        try:
            code=child.wait(timeout=remaining())
        except (subprocess.TimeoutExpired,TimeoutError):
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            status('timeout_inconclusive');return
    if code:
        status('native_nonpass',exit_code=code);return
    status('assessing_terminal_native_waveform')
    wave=out/'duration.prn';times,_=waveform(wave)
    assert times[-1]>=160e-9-1e-15
    edges=independent_edges(wave);rows=[]
    for start,stop in plan['predeclared_windows_ns']:
        remaining();metric=measure(wave,start,stop,1.8,min_periods=3)
        frequency,drift=decimal_measure(edges,start,stop)
        assert abs(float(frequency)-metric['mhz'])<1e-8
        assert abs(float(drift)-metric['half_window_difference_mhz'])<1e-8
        row=dict(start_ns=start,stop_ns=stop,**metric,
                 independent_decimal_frequency_mhz=str(frequency),
                 independent_decimal_half_window_difference_mhz=str(drift))
        if stop<=80:
            old=measure(Path(plan['reference_waveform']),start,stop,1.8,min_periods=3)
            row.update(reference_80ns_run=old,duration_run_minus_reference_mhz=metric['mhz']-old['mhz'])
        rows.append(row)
    for name,digest in pins.items():assert sha(name)==digest,name
    remaining()
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        records=rows,all_predeclared_windows_retained=True,independent_decimal_checks=len(rows),
        pvt=plan['pvt'],code=247,coarse=1,stop_ns=160,native_waveform_terminal=True,
        measurement_window_adopted=False,calibration_model_qualified=False,
        dynamic_model_qualified=False,release_qualified=False,scope=__doc__))
    status('terminal_assessment',retained_windows=len(rows))


if __name__=='__main__':
    main()
