#!/usr/bin/env python3
"""Retain a bounded stiff-control timeout without treating it as model failure."""
import json,math
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];folder=root/'build/timing400/release_001/wire_preconditioned_native_controls_002'
old=json.loads((folder/'status.json').read_text());assert not process(old['runner_pid'])['live']
assert not process(old['native_pid'])['live']
receipts=json.loads((folder/'native_receipts.json').read_text())
assert receipts[-1]['timed_out'] and receipts[-1]['native_exit']==-15
summary={}
paths=[Path(__file__),folder/'native_receipts.json']
for case in ['baseline_stock','baseline_adapter']:
    log=folder/case/'native.log';wave=folder/(case+'.cir.prn');paths.extend([log,wave,folder/(case+'.cir')])
    samples=0;last=None;minimum=None
    for line in wave.open():
        f=line.split()
        if len(f)==6 and f[0].isdigit():
            t=float(f[1]);assert math.isfinite(t)
            if last is not None:
                assert t>last
                minimum=t-last if minimum is None else min(minimum,t-last)
            last=t;samples+=1
    count=0;nonpass=0;maximum=0.
    for line in log.open():
        if line.startswith('OpenPLL_wire_PC call='):
            f=dict(item.split('=',1) for item in line.split()[1:])
            if 'status' in f:
                count+=1;nonpass+=int(f['status'])!=0
                if int(f['status'])==0:maximum=max(maximum,float(f['scaled_true_relative_residual']))
    summary[case]=dict(samples=samples,simulation_time_s=last,minimum_step_s=minimum,
        adapter_linear_solves=count,rejected_linear_solves=nonpass,maximum_successful_linear_relative_residual=maximum)
assert summary['baseline_stock']['samples']>1000000
save(folder/'timeout_assessment.json',dict(timeout_inconclusive=True,previous_status=old,
    stock_baseline_completed=True,adapter_transient_incomplete=True,
    stiff_coupling_fixture_default_trapezoid=True,case_summaries=summary,
    linear_solve_accuracy_does_not_establish_transient_completion=True,
    input_sha256={str(p.resolve()):digest(p) for p in paths},release_qualified=False,adopted=False))
save(folder/'status.json',dict(state='timeout_inconclusive',runner_pid=old['runner_pid'],
    last_native_pid=old['native_pid'],native_process_stopped=True,
    timeout_assessment_sha256=digest(folder/'timeout_assessment.json'),release_qualified=False,adopted=False))
print(json.dumps(summary))
