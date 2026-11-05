#!/usr/bin/env python3
"""Check golden Xyce signed-branch realization of a positive field mass matrix.

The matrix [[2,1],[1,2]] pF is strictly passive but needs a -1pF branch
between its nodes. Compare both native time-step variants with the independent
analytic PWL response; retaining only positive scalar branches is incorrect.
"""
import csv
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
from scipy.linalg import expm
from compile_local_C_operators_v2 import digest, save


def live_engines():
    found = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            state = (p/'stat').read_text().rsplit(')', 1)[1].split()[0]
            if name in ['Xyce', 'ngspice', 'magicdnull'] and state != 'Z':
                found.append(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return found


def response(times, matrix):
    # Time units are ns, resistance kOhm and capacitance pF.
    operator = -np.linalg.inv(matrix)
    forcing = np.linalg.solve(matrix, np.array([1., 0.]))
    breaks = [(0., 0.), (1., 1.), (3., 1.), (4., 0.), (10., 0.), (11., 1.), (13., 1.), (14., 0.), (30., 0.)]
    values = []
    for t in times:
        state = np.zeros(2)
        for (a, va), (b, vb) in zip(breaks, breaks[1:]):
            if t <= a:
                break
            length = min(t, b)-a
            slope = (vb-va)/(b-a)
            # Augment the two circuit voltages with the affine input and its
            # constant slope, so the PWL convolution is an exact exponential.
            aug = np.zeros((4, 4))
            aug[:2, :2] = operator
            aug[:2, 2] = forcing
            aug[2, 3] = 1.
            initial = np.array([*state, va, slope])
            state = (expm(aug*length)@initial)[:2]
            if t <= b:
                break
        values.append(state)
    return np.array(values)


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base/'signed_C_Xyce_controls_001'
    out.mkdir(exist_ok=False)
    binary = Path('/opt/xyce/bin/Xyce')
    matrix = np.array([[2., 1.], [1., 2.]])
    assert np.linalg.eigvalsh(matrix).tolist() == [1., 3.]
    results, input_paths, artifacts = {}, [Path(__file__).resolve(), owner, binary], []
    for name, step in [('baseline', .02), ('half_step', .01)]:
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        case = out/name
        case.mkdir()
        deck = case/'control.cir'
        deck.write_text(f'''Signed local field mass matrix native control
Vsource input 0 PWL(0 0 1n 1 3n 1 4n 0 10n 0 11n 1 13n 1 14n 0 30n 0)
Rsource input a 1k
Rreturn b 0 1k
Ca a 0 3p
Cb b 0 3p
Cab a b -1p
.options TIMEINT METHOD=trap RELTOL=1e-8 ABSTOL=1e-12
.tran {step:g}n 30n 0 {step:g}n
.print TRAN FORMAT=CSV V(a) V(b)
.end
''')
        logpath = case/'native.log'
        with (base.parent/'guarded_native_admission.lock').open('a+') as admission:
            fcntl.flock(admission, fcntl.LOCK_EX)
            before = live_engines()
            assert len(before) < 4, before
            with logpath.open('x') as log:
                child = subprocess.Popen([str(binary), str(deck.resolve())], cwd=case, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
            save(case/'owner.json', dict(native_pid=child.pid, runner_pid=os.getpid(),
                previous_engines=before, deadline_uptime=deadline, automatic_identical_retry=False))
        try:
            code = child.wait(timeout=min(120., deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
            save(case/'status.json', dict(state='timeout_inconclusive'))
            raise
        assert code == 0, logpath.read_text()[-2000:]
        wave = Path(str(deck)+'.csv')
        with wave.open() as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        times = np.array([float(r['TIME'])/1e-9 for r in rows])
        actual = np.array([[float(r['V(a)']), float(r['V(b)'])] for r in rows])
        assert times[-1] >= 30.-1e-8 and len(rows) > 100
        # Independent analytic samples, including negative transient voltage
        # at b; a wrong positive Cab branch changes the sign of that response.
        indices = np.linspace(0, len(rows)-1, 101, dtype=int)
        expected = response(times[indices], matrix)
        error = float(abs(actual[indices]-expected).max())
        wrong = response(times[indices], np.array([[4., -1.], [-1., 4.]]))
        wrong_error = float(abs(actual[indices]-wrong).max())
        assert error < 1e-5 and wrong_error > .01, (error, wrong_error)
        assert np.min(actual[:, 1]) < -.01
        results[name] = dict(native_exit=code, samples=len(rows), max_step_ns=step,
            maximum_voltage_error_vs_analytic_V=error, wrong_positive_branch_error_V=wrong_error)
        input_paths.append(deck)
        artifacts.extend([wave, logpath, case/'owner.json'])
    assert results['half_step']['maximum_voltage_error_vs_analytic_V'] <= results['baseline']['maximum_voltage_error_vs_analytic_V']*1.1
    result = dict(golden_Xyce_signed_capacitor_mass_matrix_controls_passed=True, results=results,
        native_checks=2, global_analog_limit=4, native_identical_retry=False,
        actual_DCO_passivity_or_transient_accuracy_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in input_paths},
        artifacts={str(p.resolve()): digest(p) for p in artifacts})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
