#!/usr/bin/env python3
"""Gate packed-capacitor fallback paths against the unchanged simulator.

Uses the existing DCO deadline and shared four-engine admission. Does not
replace the running DCO, retry failed native cases, or qualify a release.
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
from run_DCO_domain_point_v3 import live_engines
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    out = base / 'compact_cap_excluded_paths_001'
    out.mkdir(exist_ok=False)
    inherited = base / 'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json'
    deadline = json.loads(inherited.read_text())['deadline_uptime']
    proof = base / 'wire_preconditioned_Xyce_compact_caps_001/assessment.json'
    built = json.loads(proof.read_text())
    binary = Path(built['binary'])
    stock = base / 'wire_preconditioned_Xyce_bounded_reuse_001/Xyce'
    assert built['experimental_build_completed'] and digest(binary) == built['binary_sha256']
    pins = {str(p): digest(p) for p in (Path(__file__).resolve(), inherited, proof, binary, stock)}
    save(out / 'owner.json', dict(runner_pid=os.getpid(), deadline_uptime=deadline,
         budget_restarted=False, input_sha256=pins))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state, release_qualified=False, adopted=False, **extra))
    # Each node has its own resistor and excitation. Four eligible constants
    # include signed capacitance and multiplicity. All other capacitors must
    # remain on the stock path; the probe explicitly requests lead current.
    cards = [
        ('plain', '1p'), ('multiple', '2p M=3'),
        ('signed', '-0.1p'), ('stabilizer', '1p'),
        ('initial', '1p IC=0.2'),
        ('dependent', 'C={1p*(1+0.1*V(dependent))}'),
        ('charge', 'Q={1p*V(charge)+0.05p*V(charge)*V(charge)}'),
        ('varying', 'C={CP*(1+0.1*sin(6.283185307179586*TIME/1n))}'),
        ('probed', '1p'), ('thermal', '1p TC1=0.001')]
    lines = ['Packed capacitor fallback controls', '.global_param CP=1p',
             'Vin input 0 PULSE(0 1.2 100p 50p 50p 300p 800p)']
    for name, parameters in cards:
        node = 'signed' if name == 'stabilizer' else name
        if name != 'stabilizer': lines.append(f'R{name} input {node} 200')
        lines.append(f'C{name} {node} 0 {parameters}')
    outputs = [f'V({name})' for name, _ in cards if name != 'stabilizer']
    outputs += ['I(Cprobed)', 'I(Vin)']
    lines += ['.options TIMEINT METHOD=GEAR RELTOL=1e-8 ABSTOL=1e-13',
              '.tran 1p 3n 0 1p UIC',
              '.print TRAN FORMAT=STD PRECISION=16 ' + ' '.join(outputs), '.end']
    deck = out / 'control.cir'
    deck.write_text('\n'.join(lines) + '\n')
    pins[str(deck)] = digest(deck)
    gate = base / 'compact_constant_cap_native_controls_audit_001/assessment.json'
    reservation = base / 'compact_constant_cap_control_reservation_001/owner.json'
    keeper = json.loads(reservation.read_text())['runner_pid']
    status('prepared_waiting_for_initial_native_audit', fixture_count=10)
    while not gate.exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('deadline_before_prerequisite_inconclusive'); return
        # Missing gate after both keeper and audit watcher terminate is terminal.
        watchers = [p for p in Path('/proc').iterdir() if p.name.isdigit()
                    and p.name != str(os.getpid())]
        watcher_live = False
        for p in watchers:
            try: command = (p / 'cmdline').read_bytes()
            except OSError: continue
            watcher_live |= b'watch_compact_constant_cap_native_controls.py' in command
        if not process(keeper)['live'] and not watcher_live:
            status('prerequisite_terminal_without_audit'); return
        time.sleep(5)
    audit = json.loads(gate.read_text())
    assert audit['completed_native_control_audit_passed']
    pins[str(gate)] = digest(gate)
    receipts = []
    for label, engine, enabled in [('reference', stock, False),
                                   ('packed', binary, True), ('disabled', binary, False)]:
        folder = out / label; folder.mkdir()
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        env.pop('OPENPLL_WIRE_PC', None)
        env.pop('OPENPLL_PACKED_CONSTANT_CAPS', None)
        if enabled: env['OPENPLL_PACKED_CONSTANT_CAPS'] = '1'
        child = None
        with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
            # Poll the lock so waiting cannot silently exceed the deadline.
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
        events = re.findall(r'OpenPLL_packed_constant_caps bucket=(\d+) instances=(\d+) eligible=(\d+)',
                            (folder/'native.log').read_text())
        if enabled:
            buckets = {int(b): (int(n), int(e)) for b, n, e in events}
            if 0 in buckets: assert buckets[0] == (10, 4), buckets
            else:
                assert sum(n for n, _ in buckets.values()) == 10, buckets
                assert sum(e for _, e in buckets.values()) == 4, buckets
            assert events and all(int(e) <= 4 for _, _, e in events), events
        else: assert not events
    waves = {}
    for label in ('reference', 'packed', 'disabled'):
        path = out/label/'wave.prn'; text = path.read_text()
        assert 'End of Xyce(TM) Simulation' in text
        rows = [s.split() for s in text.splitlines()[1:] if s and s.split()[0].isdigit()]
        wave = np.array([[float(x) for x in row[1:]] for row in rows])
        assert wave.shape[1] == len(outputs)+1 and np.isfinite(wave).all()
        assert wave[0, 0] == 0 and wave[-1, 0] >= 3e-9*(1-1e-12)
        assert np.all(np.diff(wave[:, 0]) > 0)
        waves[label] = wave; pins[str(path)] = digest(path)
    comparisons = []
    grid = np.linspace(0, 3e-9, 6001)
    for label in ('packed', 'disabled'):
        errors = [float(np.max(np.abs(np.interp(grid, waves[label][:,0], waves[label][:,i])-
                   np.interp(grid, waves['reference'][:,0], waves['reference'][:,i]))))
                  for i in range(1, len(outputs)+1)]
        # Small-fixture equivalence tolerances, not DCO frequency qualification.
        assert max(errors[:-2]) < 1e-6 and max(errors[-2:]) < 1e-9, errors
        comparisons.append(dict(case=label, signals=outputs, maximum_absolute_differences=errors))
    for name, sha in pins.items(): assert digest(Path(name)) == sha, name
    save(out/'assessment.json', dict(input_sha256=pins, case_receipts=receipts,
         comparisons=comparisons, mixed_fixture_fallback_controls_passed=True,
         expected_eligible_constants=4, expected_excluded_instances=6,
         sensitivity_and_external_parameter_mutation_qualified=False,
         performance_qualified=False, full_DCO_qualified=False, release_qualified=False, adopted=False))
    status('completed_mixed_fixture_fallback_controls')


if __name__ == '__main__':
    main()
