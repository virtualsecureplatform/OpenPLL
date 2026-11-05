#!/usr/bin/env python3
"""Check breakpoint grid alignment against a closed-form ramp-driven RC."""
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines


def exact(t):
    tau, ramp = 1e-9, 50e-12
    u = t - 5e-9
    if u <= 0: return 1.8
    slope = -1.8 / ramp
    if u <= ramp:
        return 1.8 + slope * (u + tau * math.expm1(-u / tau))
    at_end = 1.8 + slope * (ramp + tau * math.expm1(-ramp / tau))
    return at_end * math.exp(-(u - ramp) / tau)


def main():
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base / 'breakpoint_grid_controls_001'; out.mkdir(exist_ok=False)
    binary = Path('/opt/xyce/bin/Xyce')
    inputs = [Path(__file__).resolve(), owner, binary]
    results, artifacts = [], []
    for step in ['0.5p', '0.47p']:
        folder = out / step; folder.mkdir()
        deck = folder / 'control.cir'
        deck.write_text('Breakpoint grid RC control\n'
            'VDRIVE input 0 PULSE(1.8 0 5n 50p 50p 8n 16n)\n'
            'R1 input output 1k\nC1 output 0 1p\n'
            '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0\n'
            '.options TIMEINT RELTOL=1e-6 ABSTOL=1e-10\n'
            f'.tran 20p 6n 0 {step}\n'
            '.print TRAN FORMAT=STD PRECISION=16 V(output)\n.end\n')
        inputs.append(deck)
        with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            assert len(live_engines()) < 4
            with (folder / 'native.log').open('x') as log:
                child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                    env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
            save(out / 'status.json', dict(state='native_breakpoint_control_running', native_pid=child.pid,
                runner_pid=os.getpid(), maximum_step=step, deadline_uptime=deadline))
        try: code = child.wait(timeout=min(120, deadline - time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM); child.wait(timeout=10)
            save(out / 'status.json', dict(state='timeout_inconclusive')); return
        wave = Path(str(deck) + '.prn')
        lines = wave.read_text().splitlines()
        assert lines[0].split() == ['Index', 'TIME', 'V(OUTPUT)']
        rows = [line.split() for line in lines[1:] if len(line.split()) == 3 and line.split()[0].isdigit()]
        assert all(int(row[0]) == i for i, row in enumerate(rows))
        data = [(float(row[1]), float(row[2])) for row in rows]
        assert all(math.isfinite(value) for row in data for value in row)
        assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
        tiny = min(b[0] - a[0] for a, b in zip(data, data[1:]) if 4.9e-9 <= b[0] <= 5.1e-9)
        error = max(abs(value - exact(t)) for t, value in data)
        if step == '0.47p':
            assert code == 0 and data[-1][0] >= 6e-9 * (1 - 1e-12)
            assert tiny > 1e-18 and error < 5e-6, (tiny, error)
        results.append(dict(maximum_step=step, native_exit=code, last_time_s=data[-1][0],
            minimum_step_near_breakpoint_s=tiny, maximum_closed_form_voltage_error_V=error))
        artifacts.extend([wave, folder / 'native.log'])
    save(out / 'assessment.json', dict(noncommensurate_grid_matches_analytic_RC=True, cases=results,
        maximum_step_fix='0.47ps instead of0.5ps; reset timing and tolerances unchanged',
        engine_source_modified=False, DCO_convergence_or_frequency_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(path.resolve()): digest(path) for path in inputs},
        artifacts={str(path.resolve()): digest(path) for path in artifacts}))
    save(out / 'status.json', dict(state='completed_analytic_control_passed'))
    print(json.dumps(results))


if __name__ == '__main__': main()
