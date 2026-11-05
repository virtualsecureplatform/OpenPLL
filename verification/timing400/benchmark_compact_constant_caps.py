#!/usr/bin/env python3
"""Isolate capacitor-loop cost; never extrapolate this fixture to DCO timing.

Three predeclared executions share one frozen signed 150000-capacitor deck.
Native launch requires prior mixed-fallback correctness controls and inherits
the live DCO experiment deadline, memory guard and four-engine admission cap.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time
import numpy as np
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    out = base/'compact_constant_cap_benchmark_001'; out.mkdir(exist_ok=False)
    inherited = base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json'
    deadline = json.loads(inherited.read_text())['deadline_uptime']
    proof = base/'wire_preconditioned_Xyce_compact_caps_001/assessment.json'
    build = json.loads(proof.read_text()); binary = Path(build['binary'])
    stock = base/'wire_preconditioned_Xyce_bounded_reuse_001/Xyce'
    assert build['experimental_build_completed'] and digest(binary) == build['binary_sha256']
    pins = {str(p): digest(p) for p in (Path(__file__).resolve(), inherited, proof, binary, stock)}
    prerequisite = base/'compact_cap_excluded_paths_001'
    prior_owner = json.loads((prerequisite/'owner.json').read_text())
    variants = [('reference', stock, False), ('packed', binary, True), ('disabled', binary, False)]
    save(out/'owner.json', dict(runner_pid=os.getpid(), deadline_uptime=deadline,
         budget_restarted=False, fixture_capacitors=150000, fixture_nodes=64,
         declared_variants=[v[0] for v in variants], per_case_wall_limit_s=120,
         prerequisite_runner_pid=prior_owner['runner_pid'], input_sha256=pins))
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, adopted=False, **extra))
    deck = out/'benchmark.cir'
    with deck.open('x') as handle:
        handle.write('Signed constant capacitor loop benchmark\n')
        handle.write('Vin input 0 PULSE(0 1.2 20p 10p 10p 100p 250p)\n')
        for i in range(64): handle.write(f'R{i} input n{i} {1000+10*i}\n')
        for i in range(150000):
            first = i % 64
            second = '0' if i % 3 == 0 else f'n{(first+1+(i//64)%31)%64}'
            value = '-1e-19' if i % 17 == 0 else '1e-17'
            multiple = ' M=2' if i % 23 == 0 else ''
            handle.write(f'C{i} n{first} {second} {value}{multiple}\n')
        handle.write('.options TIMEINT METHOD=GEAR RELTOL=1e-7 ABSTOL=1e-12\n')
        handle.write('.tran 1p 500p 0 1p\n')
        handle.write('.print TRAN FORMAT=STD PRECISION=16 '+
                     ' '.join(f'V(n{i})' for i in range(64))+' I(Vin)\n.end\n')
    pins[str(deck)] = digest(deck)
    status('prepared_waiting_for_fallback_correctness_gate')
    gate = prerequisite/'assessment.json'
    while not gate.exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('deadline_before_prerequisite_inconclusive'); return
        live = process(prior_owner['runner_pid'])
        if not live['live'] or not any(s.endswith('check_compact_cap_excluded_paths.py') for s in live['argv']):
            status('prerequisite_terminal_without_pass', prerequisite_runner=live); return
        time.sleep(5)
    assert json.loads(gate.read_text())['mixed_fixture_fallback_controls_passed']
    pins[str(gate)] = digest(gate)
    receipts = []
    for label, engine, enabled in variants:
        folder = out/label; folder.mkdir()
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        env.pop('OPENPLL_WIRE_PC', None); env.pop('OPENPLL_PACKED_CONSTANT_CAPS', None)
        if enabled: env['OPENPLL_PACKED_CONSTANT_CAPS'] = '1'
        child = None
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            while time.clock_gettime(time.CLOCK_BOOTTIME) < deadline:
                try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    status('queued_for_admission_lock', case=label); time.sleep(1); continue
                active = live_engines()
                memory = {s.split(':')[0]: int(s.split()[1])*1024
                          for s in Path('/proc/meminfo').read_text().splitlines()}
                if len(active) < 4 and memory['MemAvailable'] >= 8*1024**3:
                    def limits():
                        resource.setrlimit(resource.RLIMIT_AS, (6*1024**3, 6*1024**3))
                        resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
                    command = [str(engine), '-quiet', '-linsolv', 'KLU', '-o', str(folder/'wave'), str(deck)]
                    started = time.monotonic()
                    with (folder/'native.log').open('x') as log:
                        child = subprocess.Popen(command, cwd=folder, env=env, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
                    save(folder/'launch.json', dict(native_pid=child.pid, command=command,
                         native_before=active, maximum_native_workers=4, automatic_identical_retry=False))
                    break
                fcntl.flock(lock, fcntl.LOCK_UN)
                status('queued_for_native_capacity', case=label, observed_native_pids=active)
                time.sleep(2)
        if child is None: status('deadline_before_admission_inconclusive', case=label); return
        status('native_running', case=label, native_pid=child.pid)
        try: code = child.wait(timeout=min(120, max(.001, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            code = child.returncode
        receipts.append(dict(case=label, native_exit=code, elapsed_s=time.monotonic()-started))
        save(out/'native_receipts.json', receipts)
        if code != 0: status('native_nonpass', case=label, native_exit=code); return
    waves = {}; metrics = {}
    for label, _, enabled in variants:
        folder = out/label; log = (folder/'native.log').read_text()
        assert 'End of Xyce(TM) Simulation' in log
        events = re.findall(r'OpenPLL_packed_constant_caps bucket=(\d+) instances=(\d+) eligible=(\d+)', log)
        if enabled:
            assert events and any(int(n)==150000 for _, n, _ in events)
            assert all(int(n)==int(e) for _, n, e in events)
        else: assert not events
        segment = log.split('***** Transient Stepping time:')[1].split('***** Solution Summary')[0]
        metrics[label] = {'transient_stepping_s': float(segment.split()[0])}
        for title, key in [('Total Residual Load Time', 'residual_load_s'),
                           ('Total Jacobian Load Time', 'jacobian_load_s'),
                           ('Total Linear Solution Time', 'linear_solution_s'),
                           ('Number Successful Steps Taken', 'successful_steps'),
                           ('Number Failed Steps Attempted', 'failed_steps')]:
            match = re.search(re.escape(title)+r':\s*([\d.eE+-]+)', segment)
            assert match, title
            metrics[label][key] = float(match.group(1))
        assert metrics[label]['successful_steps'] >= 500
        wavepath = folder/'wave.prn'; text = wavepath.read_text()
        assert 'End of Xyce(TM) Simulation' in text
        rows = [line.split() for line in text.splitlines()[1:] if line and line.split()[0].isdigit()]
        wave = np.array([[float(x) for x in row[1:]] for row in rows])
        assert wave.shape[1] == 66 and np.isfinite(wave).all()
        assert wave[0,0] == 0 and wave[-1,0] >= 500e-12*(1-1e-12)
        assert np.all(np.diff(wave[:,0]) > 0)
        waves[label] = wave
        for p in (wavepath, folder/'native.log', folder/'launch.json'): pins[str(p)] = digest(p)
    comparisons = []; grid = np.linspace(0, 500e-12, 2001)
    for label in ('packed', 'disabled'):
        differences = [float(np.max(np.abs(np.interp(grid, waves[label][:,0], waves[label][:,i])-
                       np.interp(grid, waves['reference'][:,0], waves['reference'][:,i]))))
                       for i in range(1, 66)]
        assert max(differences[:-1]) < 1e-6 and differences[-1] < 1e-9, differences
        comparisons.append(dict(case=label, maximum_node_voltage_difference_V=max(differences[:-1]),
                                supply_current_difference_A=differences[-1]))
    ratios = {key: metrics['disabled'][key]/metrics['packed'][key]
              for key in ('transient_stepping_s', 'residual_load_s', 'jacobian_load_s', 'linear_solution_s')
              if metrics['packed'][key] > 0}
    for name, sha in pins.items(): assert digest(Path(name)) == sha, name
    save(out/'assessment.json', dict(input_sha256=pins, case_receipts=receipts,
         fixture_waveform_controls_passed=True, comparisons=comparisons,
         native_metrics=metrics, disabled_over_packed_time_ratios=ratios,
         fixture_is_small_node_count_many_capacitor_kernel=True,
         statistical_performance_repeatability_qualified=False,
         full_DCO_speedup_inferred=False, live_DCO_modified=False,
         release_qualified=False, adopted=False))
    status('completed_fixture_benchmark')


if __name__ == '__main__':
    main()
