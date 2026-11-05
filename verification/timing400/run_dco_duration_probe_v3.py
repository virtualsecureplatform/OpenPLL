#!/usr/bin/env python3
"""Run a prepared duration comparison once and retain all measurement windows.

Uses serialized guarded admission, unchanged KLU settings and the original12h
absolute budget including dependency wait/admission/assessment. A preceding external
runner must have launched before this runner begins competing for capacity. A settling observation is not a calibration
uncertainty bound, dynamic DCO model, adopted window or release qualification.
"""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from audit_dco_settling_windows import independent_edges
from benchmark_dco_linear_solver_v2 import waveform
from characterize_compact_propagation import ROOT, XYCE
from guarded_native_admission import AdmissionDeferred, launch as guarded_launch
from run_dco_qualification import measure, sha, save


def decimal_measure(edges, start_ns, stop_ns):
    chosen = [t for t in edges if Decimal(start_ns)*Decimal('1e-9') <= t <= Decimal(stop_ns)*Decimal('1e-9')]
    assert len(chosen) >= 4
    middle = (len(chosen)-1)//2
    with localcontext() as context:
        context.prec = 40
        frequency = Decimal(len(chosen)-1)/(chosen[-1]-chosen[0])*Decimal('1e-6')
        first = Decimal(middle)/(chosen[middle]-chosen[0])*Decimal('1e-6')
        last = Decimal(len(chosen)-1-middle)/(chosen[-1]-chosen[middle])*Decimal('1e-6')
    return frequency, abs(first-last)


def main():
    deadline = None
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical-workspace', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--after-launch', required=True, type=Path,
                        help='Wait for the preceding external runner to complete its admission')
    parser.add_argument('--controller-pid', required=True, type=int)
    parser.add_argument('--handoff-receipt', required=True, type=Path)
    parser.add_argument('--absolute-deadline-uptime', required=True, type=float)
    args = parser.parse_args()
    handoff_path = args.handoff_receipt.resolve()
    handoff = json.loads(handoff_path.read_text())
    assert handoff['native_launch_ever_occurred'] is False
    assert handoff['absolute_deadline_uptime'] == args.absolute_deadline_uptime
    assert abs(args.absolute_deadline_uptime-(handoff['old_runner_start_ticks']/os.sysconf('SC_CLK_TCK')+43200)) < 1e-6
    old_proc = Path('/proc')/str(handoff['old_runner_pid'])
    assert not old_proc.exists() or (old_proc/'stat').read_text().rsplit(')',1)[1].split()[0] == 'Z'
    old_claim = Path(handoff['old_claim'])
    assert sha(old_claim) == handoff['old_claim_sha256']
    deadline = args.absolute_deadline_uptime
    assert 0 < deadline-time.clock_gettime(time.CLOCK_BOOTTIME) <= 43200
    assert ROOT == args.canonical_workspace.resolve(), 'Canonical host absolute script path required'
    path, out = args.plan.resolve(), args.output.resolve()
    plan = json.loads(path.read_text())
    assert plan['pvt'] == dict(corner='tt', temperature_c=27, supply_v=1.8)
    assert plan['stop_ns'] in (160, 200) and plan['reference_stop_ns'] == 80
    assert plan['solver'] == 'KLU' and not plan['calibration_model_qualified']
    pins = {**plan['input_sha256'], str(path): sha(path), str(handoff_path): sha(handoff_path), str(old_claim): sha(old_claim)}
    for name in ('run_dco_duration_probe_v3.py', 'guarded_native_admission.py', 'audit_dco_settling_windows.py',
                 'benchmark_dco_linear_solver_v2.py', 'characterize_compact_propagation.py',
                 'run_dco_qualification.py'):
        dep = Path(__file__).with_name(name).resolve()
        pins[str(dep)] = sha(dep)
    for name, digest in pins.items():
        assert sha(name) == digest, name
    assert str(out) == handoff['output']
    assert out.exists() and not (out/'launch.json').exists() and not (out/'run.log').exists()
    assert {p.name for p in out.iterdir()} <= {'status.json','admission.json','dependency_admission_complete.json',handoff_path.name}
    with (path.parent/'native_run_v3.json').open('x') as stream:
        json.dump(dict(runner_pid=os.getpid(), output=str(out),
             started_utc=datetime.now(timezone.utc).isoformat(), original_claim=str(old_claim),
             absolute_deadline_uptime=deadline, automatic_identical_retry=False), stream, indent=2)

    def status(state, **fields):
        save(out/'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             total_budget_s=43200, absolute_deadline_uptime=deadline, runner_pid=os.getpid(),
             release_qualified=False, **fields))

    def remaining():
        value = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if value <= 0:
            status('timeout_inconclusive')
            raise TimeoutError('total12h budget exhausted')
        return value

    # Only one external owner may compete for admission. The previous runner
    # writes launch.json after Popen and never returns to admission afterward.
    # Dependency waiting consumes this probe's existing total12h budget.
    after = args.after_launch.resolve()
    assert after.name == 'launch.json' and after != out/'launch.json'
    dependency_status = after.parent/'status.json'
    while not after.exists():
        remaining()
        if dependency_status.exists():
            state = json.loads(dependency_status.read_text())['state']
            if state in ('timeout_inconclusive', 'native_nonpass', 'prerequisite_nonpass_no_native_launch'):
                status('dependency_terminal_without_native_launch', prerequisite=str(after))
                return
        status('waiting_for_preceding_external_launch', prerequisite=str(after))
        time.sleep(min(30, remaining()))
    preceding = json.loads(after.read_text())
    assert preceding['command'][0] == str(XYCE)
    assert preceding['input_sha256']
    for name, digest in preceding['input_sha256'].items():
        assert sha(name) == digest, name
        assert name not in pins or pins[name] == digest, name
        pins[name] = digest
    pins[str(after)] = sha(after)
    save(out/'dependency_admission_complete_v3.json', dict(prerequisite=str(after),
         prerequisite_sha256=pins[str(after)], preceding_native_pid=preceding['pid'],
         total_budget_remaining_s=remaining(), release_qualified=False))
    command = [str(XYCE), '-linsolv', 'KLU', '-quiet', '-o', str(out/'duration'), str(path.parent/'duration.spice')]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with (out/'run.log').open('x') as stream:
        while True:
            remaining()
            try:
                child = guarded_launch(command, env, stream, args.controller_pid,
                                       out/'guarded_admission_v3.json')
                break
            except AdmissionDeferred as error:
                status('waiting_for_guarded_native_capacity', reason=str(error))
                time.sleep(min(30, remaining()))
        save(out/'launch.json', dict(pid=child.pid, command=command, input_sha256=pins, total_budget_s=43200))
        status('native_running', native_pid=child.pid)
        try:
            code = child.wait(timeout=remaining())
        except (subprocess.TimeoutExpired, TimeoutError):
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            status('timeout_inconclusive', native_pid=child.pid)
            return
    if code:
        status('native_nonpass', exit_code=code)
        return
    status('assessing_terminal_native_waveform')
    wave = out/'duration.prn'
    times, _ = waveform(wave)
    assert times[-1] >= plan['stop_ns']*1e-9-1e-15
    edges = independent_edges(wave)
    rows = []
    for start, stop in plan['predeclared_windows_ns']:
        remaining()
        metric = measure(wave, start, stop, 1.8, min_periods=3)
        frequency, drift = decimal_measure(edges, start, stop)
        assert abs(float(frequency)-metric['mhz']) < 1e-8
        assert abs(float(drift)-metric['half_window_difference_mhz']) < 1e-8
        row = dict(start_ns=start, stop_ns=stop, **metric,
                   independent_decimal_frequency_mhz=str(frequency),
                   independent_decimal_half_window_difference_mhz=str(drift))
        if stop <= 80:
            old = measure(Path(plan['reference_waveform']), start, stop, 1.8, min_periods=3)
            row.update(reference_80ns_run=old, duration_run_minus_reference_mhz=metric['mhz']-old['mhz'])
        rows.append(row)
    for name, digest in pins.items():
        assert sha(name) == digest, name
    remaining()
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'},
        records=rows, all_predeclared_windows_retained=True, independent_decimal_checks=len(rows),
        pvt=plan['pvt'], code=plan['code'], coarse=plan['coarse'], stop_ns=plan['stop_ns'],
        native_waveform_terminal=True, measurement_window_adopted=False,
        calibration_model_qualified=False, dynamic_model_qualified=False, release_qualified=False,
        scope=__doc__))
    status('terminal_assessment', retained_windows=len(rows))


if __name__ == '__main__':
    main()
