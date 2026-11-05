#!/usr/bin/env python3
"""Audit completed native ideal-wire data and report settling diagnostics only."""
import json
import math
from pathlib import Path
import statistics
import time
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    folder = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001'
    proof_path = folder / 'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['native_exit'] == 0 and proof['completed_diagnostic_oscillation']
    assert proof['native_ideal_wire_reference'] and not proof['physical_wire_R_present']
    for name, value in {**proof['input_sha256'], **proof['artifacts']}.items():
        assert digest(Path(name)) == value, name
    wave = folder / 'point.cir.prn'
    lines = wave.read_text().splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    assert lines[-1] == 'End of Xyce(TM) Simulation'
    data = []
    for line in lines[1:-1]:
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(data)
        data.append(tuple(float(value) for value in fields[1:]))
    assert all(math.isfinite(value) for row in data for value in row)
    assert data[0][0] == 0 and data[-1][0] >= 80e-9 * (1 - 1e-12)
    assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
    edges = []
    for a, b in zip(data, data[1:]):
        if a[1] < .9 <= b[1]:
            edges.append(a[0] + (.9 - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    selected = [edge for edge in edges if edge >= 20e-9]
    mhz = (len(selected) - 1) / (selected[-1] - selected[0]) * 1e-6
    assert abs(mhz - proof['metrics']['mhz']) < 1e-9
    windows = []
    for start in range(20, 80, 10):
        sample = [edge for edge in edges if start * 1e-9 <= edge < (start + 10) * 1e-9]
        assert len(sample) >= 3
        periods = [b - a for a, b in zip(sample, sample[1:])]
        windows.append(dict(start_ns=start, end_ns=start + 10, periods=len(periods),
            frequency_mhz=(len(sample) - 1) / (sample[-1] - sample[0]) * 1e-6,
            minimum_period_ps=min(periods) * 1e12, maximum_period_ps=max(periods) * 1e12,
            sample_period_std_ps=statistics.stdev(periods) * 1e12))
    spread = (max(row['frequency_mhz'] for row in windows) - min(row['frequency_mhz'] for row in windows)) / mhz * 1e6
    out = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_checks_001'
    out.mkdir(exist_ok=False)
    inputs = [Path(__file__).resolve(), owner, proof_path, folder / 'input_manifest.json', wave]
    result = dict(terminal_native_ideal_wire_diagnostic_verified=True,
        native_exit=0, duration_ns=80, measured_frequency_mhz=mhz,
        measured_periods=len(selected) - 1, samples=len(data), windows=windows,
        ten_ns_window_frequency_spread_ppm=spread,
        ideal_wire_only=True, physical_finite_R_range_or_calibration_qualified=False,
        independent_timestep_tolerance_duration_checked=False,
        period_variation_is_not_physical_noise_jitter_qualification=True,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(path.resolve()): digest(path) for path in inputs})
    save(out / 'assessment.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'input_sha256'}))


if __name__ == '__main__': main()
