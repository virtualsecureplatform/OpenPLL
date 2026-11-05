#!/usr/bin/env python3
"""Assess retained native split-DC controls without repeating simulations.

Constant capacitors contribute no DC current. Compare full vs C-free bias,
then full transient vs C-free-bias IC/UIC startup, including a BSIM inverter.
This does not qualify DCO frequency, settling or reduced dynamic circuitry.
"""
import csv
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import numpy as np

from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines, model_files


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base/'split_DC_initialization_controls_001'
    assert out.is_dir() and not (out/'assessment.json').exists()
    pdk = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    model = pdk/'sky130.lib.spice'
    binary = Path('/opt/xyce/bin/Xyce')
    common = f'''Split DC initial-condition control
.lib "{model}" tt
VDD vdd 0 DC 1.8
Vin input 0 DC 1.8 PWL(0 1.8 2n 1.8 2.05n 0 4n 0 4.05n 1.8 6n 1.8 6.05n 0 8n 0)
Ra input a 1k
Rb b 0 1k
Xn output input 0 0 sky130_fd_pr__nfet_01v8 w=0.65 l=0.15 ad=0.1 as=0.1 pd=1 ps=1
Xp output input vdd vdd sky130_fd_pr__pfet_01v8_hvt w=1 l=0.15 ad=0.1 as=0.1 pd=1 ps=1
.options DEVICE TEMP=27
.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0
.options TIMEINT RELTOL=1e-7 ABSTOL=1e-12
'''
    caps = 'Ca a 0 3p\nCb b 0 3p\nCab a b -1p\nCload output 0 10f\n'
    inputs = [Path(__file__).resolve(), owner, binary, *model_files(model, deadline)]
    artifacts = []
    full_bias = out/'full/operating.ic'
    free_bias = out/'C_free_DC/operating.ic'
    full = out/'full'
    free = out/'C_free_DC'
    for case in ['full', 'C_free_DC', 'saved_IC_UIC']:
        folder = out/case
        assert 'End of Xyce(TM) Simulation' in (folder/'native.log').read_text()
        artifacts.extend(p for p in folder.iterdir() if p.is_file())
    def bias(path):
        values = {}
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('*'):
                continue
            match = re.match(r'\s*\.IC\s+V\(([^)]+)\)\s*=?\s*([-+.eE0-9]+)\s*$', line, re.I)
            assert match, line
            values[match[1].upper()] = float(match[2])
        assert values
        return values
    a, b = bias(full_bias), bias(free_bias)
    assert a.keys() == b.keys()
    bias_error = max(abs(a[n]-b[n]) for n in a)
    assert bias_error < 1e-10 and abs(b['A']-1.8) < 1e-10 and abs(b['B']) < 1e-10
    restored = out/'saved_IC_UIC'
    def wave(folder):
        # Explicit Xyce -o selects its standard .prn writer on this build.
        # Read retained output; never repeat a completed native experiment.
        lines = (folder/'control.cir.prn').read_text().splitlines()
        assert lines[0].split() == ['Index', 'TIME', 'V(A)', 'V(B)', 'V(OUTPUT)']
        rows = [line.split() for line in lines[1:] if len(line.split()) == 5]
        assert all(int(row[0]) == i for i, row in enumerate(rows))
        return np.asarray([[float(v) for v in row[1:]] for row in rows])
    first, second = wave(full), wave(restored)
    assert first[-1, 0] >= 8e-9*(1-1e-8) and second[-1, 0] >= 8e-9*(1-1e-8)
    times = np.linspace(0, 8e-9, 8001)
    error = [float(max(abs(np.interp(times, first[:, 0], first[:, k])-np.interp(times, second[:, 0], second[:, k])))) for k in range(1, 4)]
    assert max(error[:2]) < 1e-5 and error[2] < 2e-3, error
    # Nonzero initial capacitor charge must be reconstructed; zero-state UIC
    # would produce a large initial transient before the first source event.
    initial = second[second[:, 0] < 1e-9]
    initial_error = max(float(max(abs(initial[:, 1]-1.8))), float(max(abs(initial[:, 2]))))
    assert initial_error < 1e-6
    inputs.extend([free_bias, Path(__file__).with_name('check_split_DC_initialization.py')])
    result = dict(native_full_and_C_free_DC_bias_equivalence_passed=True,
        native_saved_IC_UIC_linear_and_BSIM_transient_control_passed=True,
        nonzero_initial_charge_preserved=True, maximum_bias_difference_V=bias_error,
        maximum_interpolated_waveform_differences_V=error, initial_charge_voltage_error_V=initial_error,
        native_cases=3, native_cases_repeated=0, reader_corrected_from_CSV_to_retained_STD=True, actual_DCO_split_startup_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in artifacts})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed', controls_passed=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']}, indent=2))


if __name__ == '__main__':
    main()
