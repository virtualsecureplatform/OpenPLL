#!/usr/bin/env python3
"""Separate saved-bias precision and voltage-limiting effects in static BSIM controls."""
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import numpy as np
from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines


def table(path):
    lines = path.read_text().splitlines()
    assert lines[-1] == 'End of Xyce(TM) Simulation'
    header = lines[0].split(); rows = []
    for line in lines[1:-1]:
        fields = line.split(); assert len(fields) == len(header)
        assert int(fields[0]) == len(rows)
        values = list(map(float, fields[1:])); assert all(math.isfinite(v) for v in values)
        rows.append(values)
    return header[1:], np.asarray(rows)


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    terminal = base / 'campaign_deadline_001/assessment.json'
    assert json.loads(terminal.read_text())['original_runs_stopped']
    prior = base / 'static_BSIM_UIC_startup_controls_001'
    discovery = prior / 'input_0/dc/coarse.ic'
    assert discovery.exists()
    output_nodes = [re.fullmatch(r'\.IC V\(([^)]+)\) = (\S+)', line)[1]
                    for line in discovery.read_text().splitlines()]
    voltage_columns = ' '.join(f'V({node})' for node in output_nodes)
    out = base / 'static_BSIM_UIC_startup_controls_002'; out.mkdir(exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 180
    save(out / 'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        independent_static_initializer_control=True, local_limit_s=180, deadline_uptime=deadline,
        completed_campaign_extended=False, native_DCO_restarted=False))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(),
            release_qualified=False, adopted=False, **extra))
    binary = Path('/opt/xyce/bin/Xyce')
    lib = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
    pins = {str(p.resolve()): digest(p) for p in [Path(__file__), binary, lib, terminal, discovery]}
    receipts, artifacts = [], []
    def run(folder, text):
        folder.mkdir(); deck = folder / 'control.cir'; deck.write_text(text)
        pins[str(deck.resolve())] = digest(deck)
        with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX); assert len(live_engines()) < 4
            remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME); assert remaining > 0
            with (folder / 'native.log').open('x') as log:
                child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
            status('static_initializer_control_running', case=str(folder.name), native_pid=child.pid)
        try: code = child.wait(timeout=min(30, remaining))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            status('timeout_inconclusive', case=str(folder.name)); raise
        receipts.append(dict(case=str(folder.relative_to(out)), native_exit=code))
        save(out / 'native_receipts.json', receipts)
        assert code == 0, (folder / 'native.log').read_text()[-1500:]
        wave = Path(str(deck) + '.prn'); artifacts.extend([wave, folder / 'native.log'])
        return table(wave)
    results = []
    for number, level in enumerate([0., .617283941, 1.8]):
        folder = out / f'input_{number}'; folder.mkdir()
        common = f'''Static BSIM initialization control
.lib "{lib}" tt
VDD vdd 0 1.8
Vin input 0 {level:.17g}
Ra input a 1k
Rb b 0 1k
Xn output input 0 0 sky130_fd_pr__nfet_01v8 w=0.65 l=0.15 ad=0.1 as=0.1 pd=1 ps=1
Xp output input vdd vdd sky130_fd_pr__pfet_01v8_hvt w=1 l=0.15 ad=0.1 as=0.1 pd=1 ps=1
Ca a 0 3p
Cb b 0 3p
Cab a b -1p
Cload output 0 10f
.options DEVICE TEMP=27
.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0
.options TIMEINT RELTOL=1e-7 ABSTOL=1e-12
'''
        coarse = folder / 'dc/coarse.ic'
        header, dc = run(folder / 'dc', common + f'.SAVE TYPE=IC FILE={coarse.resolve()}\n'
            f'.dc VDD 1.8 1.8 .1\n.print DC FORMAT=STD PRECISION=17 {voltage_columns}\n.end\n')
        assert len(dc) == 1 and all(name.startswith('V(') and name.endswith(')') for name in header)
        precise = {name[2:-1].upper(): float(value) for name, value in zip(header, dc[0])}
        saved = {}
        for line in coarse.read_text().splitlines():
            match = re.fullmatch(r'\.IC V\(([^)]+)\) = (\S+)', line)
            assert match; saved[match[1].upper()] = float(match[2])
        assert precise.keys() == saved.keys(), (precise.keys() - saved.keys(), saved.keys() - precise.keys())
        high = folder / 'high_precision.ic'
        high.write_text(''.join(f'.IC V({name}) = {value:.17g}\n' for name, value in precise.items()))
        for path in [coarse, high]: pins[str(path.resolve())] = digest(path)
        directive = '.tran .25p 20p 0 .25p{uic}\n.print TRAN FORMAT=STD PRECISION=17 V(a) V(b) V(output) I(VDD)\n.end\n'
        _, reference = run(folder / 'ordinary_DC_startup', common + directive.format(uic=''))
        assert reference[-1, 0] >= 20e-12 * (1 - 1e-10) and np.all(np.diff(reference[:, 0]) > 0)
        grid = np.linspace(0, 20e-12, 401); cases = []
        for name, bias, limiting in [('coarse_limited', coarse, 1), ('precise_limited', high, 1),
                                      ('precise_unlimited', high, 0)]:
            text = common.replace('.options DEVICE TEMP=27', f'.options DEVICE TEMP=27 VOLTLIM={limiting}')
            _, values = run(folder / name, text + f'.include "{bias.resolve()}"\n' + directive.format(uic=' UIC'))
            assert values[-1, 0] >= 20e-12 * (1 - 1e-10) and np.all(np.diff(values[:, 0]) > 0)
            errors = [float(max(abs(np.interp(grid, values[:, 0], values[:, i]) -
                np.interp(grid, reference[:, 0], reference[:, i])))) for i in range(1, 5)]
            cases.append(dict(case=name, maximum_voltage_differences_V=errors[:3],
                maximum_supply_current_difference_A=errors[3], samples=len(values),
                largest_output_departure_from_DC_V=float(max(abs(values[:, 3] - precise['OUTPUT'])))))
        results.append(dict(input_voltage_V=level, exported_voltages=len(saved),
            maximum_save_rounding_error_V=max(abs(precise[n] - saved[n]) for n in saved),
            reference_samples=len(reference), cases=cases))
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(out / 'assessment.json', dict(static_BSIM_initializer_comparison_completed=True, results=results,
        initialization_cause_in_full_DCO_proven=False, full_DCO_speedup_demonstrated=False,
        full_DCO_restarted=False, completed_campaign_extended=False,
        release_qualified=False, adopted=False, input_sha256=pins,
        artifacts={str(p.resolve()): digest(p) for p in artifacts}))
    status('completed_static_initializer_controls')


if __name__ == '__main__':
    main()
