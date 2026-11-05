#!/usr/bin/env python3
"""Guarded refinement observations under the existing shared timing deadline."""
import argparse
from array import array
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines
from run_compact_capture_boundaries_v2 import observe
from run_DCO_gear_fallback_v3 import admission_lock


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--admission-lock-fd',type=int,required=True);args=parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    folder = base / 'capture_aperture_refinement_fs125_001'
    plan_path = folder / 'plan.json'
    plan = json.loads(plan_path.read_text())
    deadline = plan['shared_deadline_uptime']
    assert len(plan['fixtures']) == 90 and plan['new_interior_samples'] == 54
    assert sum(c['sentinel'] for c in plan['fixtures']) == 36
    assert plan['pvt'] == dict(corner='fs', temperature_c=125, supply_v=1.8)
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = folder / 'run_002'
    out.mkdir(exist_ok=False)
    child = None
    pins = dict(plan['input_sha256'])
    for path in (Path(__file__).resolve(), plan_path,
                 Path(__file__).with_name('run_compact_capture_boundaries_v2.py'),
                 Path(__file__).with_name('characterize_compact_propagation.py'),
                 Path(__file__).with_name('run_DCO_domain_point_v3.py'),
                 Path(__file__).with_name('compile_local_C_operators_v2.py'),
                 Path(__file__).with_name('run_DCO_gear_fallback_v3.py')):
        pins[str(path)] = digest(path)

    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(),
            observed_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
            release_qualified=False, adopted=False, **extra))

    def remaining():
        seconds = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if seconds <= 0:
            raise TimeoutError('inherited timing-campaign deadline reached')
        return seconds

    def stop():
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (6*1024**3, 6*1024**3))
        cpu_seconds = max(1, int(remaining()))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds+1))

    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        inherited_owner=plan['inherited_campaign_owner'], budget_restarted=False,
        maximum_native_workers=4, address_space_limit_GiB=6,
        queued_sequential_workers_have_priority=False, next_slot_priority_handoff=True, automatic_identical_retry=False))
    try:
        status('checking_frozen_inputs')
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        while True:
            remaining()
            with admission_lock(base,args.admission_lock_fd) as lock:
                args.admission_lock_fd=None
                fcntl.flock(lock, fcntl.LOCK_EX)
                active = live_engines()
                priority = []
                mem = {line.split(':', 1)[0]: int(line.split()[1])*1024
                       for line in Path('/proc/meminfo').read_text().splitlines()}
                if len(active) < 4 and not priority and mem['MemAvailable'] >= 8*1024**3:
                    command = ['/opt/xyce/bin/Xyce', '-linsolv', 'KLU', '-quiet',
                               '-o', str(out / 'batch'), str(folder / 'batch.cir')]
                    with (out / 'run.log').open('x') as log:
                        started = time.clock_gettime(time.CLOCK_BOOTTIME)
                        child = subprocess.Popen(command, cwd=out, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits,
                            env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'))
                    save(out / 'launch.json', dict(pid=child.pid, command=command,
                        input_sha256=pins, native_before=active, deadline_uptime=deadline))
                    status('native_running', native_pid=child.pid)
                    break
            status('queued_for_shared_native_capacity', observed_native_pids=active,
                   higher_priority_sequential_pids=priority)
            time.sleep(min(5, remaining()))
        try:
            code = child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            raise TimeoutError('inherited deadline reached during native run')
        save(out / 'native_exit.json', dict(native_exit=code,
            elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started))
        if code:
            status('native_nonpass', native_exit=code)
            return
        remaining()
        status('assessing_terminal_waveform')
        columns = plan['waveform_columns']
        times, values, terminal = array('d'), [array('d') for _ in columns], False
        with (out / 'batch.prn').open() as stream:
            assert stream.readline().split() == ['Index', 'TIME', *columns]
            for line in stream:
                if 'End of Xyce(TM) Simulation' in line:
                    assert not terminal
                    terminal = True
                    continue
                row = line.split()
                if not row:
                    continue
                assert not terminal and int(row[0]) == len(times)
                numbers = list(map(float, row[1:]))
                assert len(numbers) == len(columns)+1 and all(map(math.isfinite, numbers))
                times.append(numbers[0])
                for series, value in zip(values, numbers[1:]):
                    series.append(value)
                if len(times) % 1000 == 0:
                    remaining()
        assert terminal and times[0] == 0 and times[-1] >= 28e-9-1e-15
        assert all(a < b for a, b in zip(times, times[1:]))
        records = []
        for index, case in enumerate(plan['fixtures']):
            remaining()
            record = dict(case_index=index, observation_integrity_passed=False)
            try:
                record.update(observe(times, values[4*index:4*index+4], case),
                              observation_integrity_passed=True)
            except AssertionError:
                record['reason'] = 'initial/pretest state, source timing or observation horizon failed'
            records.append(record)
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        artifacts = {}
        for path in out.iterdir():
            remaining()
            if path.is_file() and path.name != 'status.json':
                artifacts[str(path)] = digest(path)
        controls = [r for r, c in zip(records, plan['fixtures']) if c['sentinel']]
        remaining()
        save(out / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
            records=records, fixtures=len(records), new_interior_samples=54,
            observation_integrity_passing=sum(r['observation_integrity_passed'] for r in records),
            separated_controls=36, separated_controls_passing=sum(r.get('sentinel_passed', False) for r in controls),
            all_native_waveform_events_terminal=True, pvt=plan['pvt'],
            setup_hold_recovery_removal_qualified=False, numerical_domain_enclosure_qualified=False,
            physical_timing_qualified=False, release_qualified=False, adopted=False))
        status('terminal_assessment', fixtures=90,
               observation_integrity_passing=sum(r['observation_integrity_passed'] for r in records),
               separated_controls_passing=sum(r.get('sentinel_passed', False) for r in controls))
    except TimeoutError as error:
        stop()
        status('timeout_inconclusive', reason=str(error))
    except Exception as error:
        stop()
        save(out / 'runner_failure.json', dict(error_type=type(error).__name__, message=str(error)))
        status('runner_nonpass')
        raise
    finally:
        stop()


if __name__ == '__main__':
    main()
