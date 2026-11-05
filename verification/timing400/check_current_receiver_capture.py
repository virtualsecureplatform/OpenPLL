#!/usr/bin/env python3
"""Prepare/run four nominal current-receiver diagnostics, not qualification.

Uses the retained fixed-rail sampled BBPD with the current max-RC event cone.
Excludes generated reset, rail noise, dynamic outside loads and metastability
bounds. One total12h deadline includes admission wait and all four points.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from characterize_compact_propagation import ROOT, PDK, XYCE
from guarded_native_admission import AdmissionDeferred, launch, scan
from run_dco_qualification import sha, save
from characterize_coupled_bbpd import coupled_deck, read_coupled_rows, capture_metrics


def verify(pins):
    for path, digest in pins.items():
        assert sha(path) == digest, path


def prepare(output):
    assert not output.exists()
    receiver = ROOT/'build/timing400/release_001/compact_event_receiver_001'
    sampled = ROOT/'build/timing450/interface_characterization/bbpd_sampled'
    receipts = [receiver/'assessment.json',
                receiver.parent/'compact_event_receiver_audit_001/assessment.json',
                sampled/'physical_assessment.json', sampled/'loaded_ss125/input_manifest.json']
    pins = {}
    for path in receipts:
        data = json.loads(path.read_text())
        for key in ('sha256', 'input_sha256', 'artifacts'):
            pins.update(data.get(key, {}))
        pins[str(path)] = sha(path)
    # Pin actual imported local Python dependencies, including indirect helpers.
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).resolve().is_relative_to(ROOT) and path.endswith('.py'):
            pins[str(Path(path).resolve())] = sha(path)
    pins[str(XYCE)] = sha(XYCE)
    verify(pins)
    model = sampled/'loaded_ss125/IntegerPLL_BBPD.reduced.spice'
    legacy_model = '/work/OpenPLL/'+str(model.relative_to(ROOT))
    assert sha(model) == pins[legacy_model]
    pins[str(model)] = pins[legacy_model]
    fixture = receiver/'receiver.max.spice'
    assert sha(fixture) == pins[str(fixture)]
    output.mkdir(parents=True)
    cases = []
    for phase in (-200, 200):
        for edge in (20, 200):
            directory = output/f'phase{phase}_edge{edge}'
            directory.mkdir()
            circuit = directory/'capture.cir'
            text = coupled_deck(PDK, model, fixture, 'tt', 1.8, 27, phase, edge)
            assert text.count('Xreceiver ') == 1 and 'CUP ' not in text and 'CDN ' not in text
            circuit.write_text(text)
            pins[str(circuit)] = sha(circuit)
            cases.append(dict(phase_ps=phase, edge_ps=edge, circuit=str(circuit)))
    verify(pins)
    save(output/'plan.json', dict(input_sha256=pins, cases=cases, pvt=dict(corner='tt',
        temperature_c=27, supply_v=1.8), receiver_rc='max', total_budget_s=43200,
        scope=__doc__, release_qualified=False))
    print('Prepared four TT27/1.8V signed capture diagnostics with current max RC.')


def run(plan_path, controller, after_launch):
    deadline = time.monotonic()+43200
    plan = json.loads(plan_path.read_text())
    assert len(plan['cases']) == 4 and plan['pvt']['supply_v'] == 1.8
    pins = {**plan['input_sha256'], str(plan_path): sha(plan_path)}
    verify(pins)
    out = plan_path.parent/'run_001'
    out.mkdir()
    save(out/'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_identical_retry=False,
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+43200))

    def status(state, **fields):
        save(out/'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_budget_s=max(0, deadline-time.monotonic()), release_qualified=False, **fields))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            raise TimeoutError('total12h budget exhausted, including admission/dependency wait')
        return value

    records = []
    child = None
    try:
        while not after_launch.exists():
            status('waiting_for_preceding_capture_scan_launch', dependency=str(after_launch))
            time.sleep(min(30, remaining()))
        for index, case in enumerate(plan['cases']):
            verify(pins)
            point = out/f'point_{index}'
            point.mkdir()
            command = [str(XYCE), '-linsolv', 'KLU', '-quiet', '-o', str(point/'capture'), case['circuit']]
            env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
            with (point/'run.log').open('x') as log:
                while True:
                    remaining()
                    try:
                        if len(scan()) >= 4:
                            raise AdmissionDeferred('four native slots occupied')
                        child = launch(command, env, log, controller, point/'guarded_admission.json')
                        break
                    except AdmissionDeferred as error:
                        status('waiting_for_guarded_native_capacity', case_index=index, reason=str(error))
                        time.sleep(min(30, remaining()))
                save(point/'launch.json', dict(pid=child.pid, command=command))
                status('native_running', case_index=index, native_pid=child.pid)
                code = child.wait(timeout=remaining())
            child = None
            if code:
                status('native_nonpass', case_index=index, exit_code=code)
                return
            text = (point/'run.log').read_text()
            assert not any(s in text for s in ('Unrecognized dot line', 'Simulation aborted', 'Netlist error'))
            rows = read_coupled_rows(point/'capture.prn')
            assert all(row[0] == i for i, row in enumerate(rows))
            metrics = capture_metrics(rows, 1.8, case['phase_ps'])
            record = dict(**case, **metrics, waveform_sha256=sha(point/'capture.prn'),
                          native_log_sha256=sha(point/'run.log'), release_qualified=False)
            save(point/'assessment.json', record)
            records.append(record)
        verify(pins)
        remaining()
        save(out/'assessment.json', dict(input_sha256=pins, results=records,
            signed_capture_passes=sum(r['direction_and_two_event_capture_pass'] for r in records),
            physical_timing_qualified=False, metastability_qualified=False,
            whole_pll_qualification_cases_passed=0, release_qualified=False, scope=__doc__))
        status('diagnostics_complete', cases_completed=len(records))
    except (TimeoutError, subprocess.TimeoutExpired):
        status('timeout_inconclusive', cases_completed=len(records))
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controller-pid', type=int)
    parser.add_argument('--after-launch', type=Path)
    args = parser.parse_args()
    assert ROOT == Path.cwd().resolve(), 'Use canonical absolute host script path and cwd'
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        assert args.controller_pid and args.after_launch
        run(args.output.resolve()/'plan.json', args.controller_pid, args.after_launch.resolve())
