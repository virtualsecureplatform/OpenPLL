#!/usr/bin/env python3
"""Audit fixed measurement windows in completed native DCO waveforms.

Retains every predeclared window. A drift below the target's 100ppm cap is
necessary, not sufficient: local LSB, variant and model-domain checks remain.
No waveform, live input, duration or acceptance criterion is changed.
"""
import argparse
from decimal import Decimal, localcontext
import json
from pathlib import Path

from run_dco_qualification import ROOT, REQUIREMENTS, measure, sha, save


def independent_edges(path):
    edges, times, terminal = [], [], False
    previous = None
    with localcontext() as context:
        context.prec = 40
        with path.open() as stream:
            assert stream.readline().split() == ['Index', 'TIME', 'V(PLLOUT)']
            for line in stream:
                if 'End of Xyce(TM) Simulation' in line:
                    terminal = True
                    continue
                row = line.split()
                if not row:
                    continue
                assert not terminal and len(row) == 3 and int(row[0]) == len(times)
                t, v = map(Decimal, row[1:])
                assert t.is_finite() and v.is_finite()
                assert not times or t > times[-1]
                if previous:
                    old_t, old_v = previous
                    if old_v < Decimal('.9') <= v:
                        edges.append(old_t+(t-old_t)*(Decimal('.9')-old_v)/(v-old_v))
                times.append(t)
                previous = t, v
        assert terminal and times[0] == 0 and times[-1] >= Decimal('80e-9')
    return edges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    spec = json.loads(REQUIREMENTS.read_text())
    assert spec['calibration_error_ppm'] == 100 and spec['voltages'] == [1.8]
    pins = {str(p): sha(p) for p in (Path(__file__).resolve(), REQUIREMENTS,
            ROOT/'scripts/dco_calibration.py', ROOT/'scripts/spice_dco_postlayout.py')}
    cases = []
    for count in (160, 144):
        screen = ROOT/f'build/timing450/dco_c1_fine_load_001/screen_{count}.json'
        pins[str(screen)] = sha(screen)
        data = json.loads(screen.read_text())
        assert data['native_complete']
        for point in data['points']:
            cases.append(dict(extra_loads=count, coarse=1, code=point['code'], target_mhz=400,
                wave=Path(point['waveform']), expected_sha256=point['waveform_sha256']))
    result = ROOT/'build/timing400/release_001/dco/n160_tt_27_c3_f247_baseline.result.json'
    pins[str(result)] = sha(result)
    data = json.loads(result.read_text())
    assert data['state'] == 'native_pass'
    cases.append(dict(extra_loads=160, coarse=3, code=247, target_mhz=300,
        wave=Path(data['metric']['waveform']), expected_sha256=data['metric']['waveform_sha256']))
    starts = [20, 30, 40, 50, 60]
    records = []
    for case in cases:
        wave = case['wave']
        assert sha(wave) == case['expected_sha256']
        provenance_path = wave.with_suffix('.provenance.json')
        provenance = json.loads(provenance_path.read_text())
        assert provenance['completed']
        param = provenance['parameters']
        assert param['corner'] == 'tt' and param['temperature_c'] == 27 and param['vdd'] == 1.8
        assert param['sim_time_ns'] == 80
        for path, digest in provenance['files'].items():
            assert sha(Path(path)) == digest, path
            assert path not in pins or pins[path] == digest
            pins[path] = digest
        for path in (wave, provenance_path):
            pins[str(path)] = sha(path)
        edges = independent_edges(wave)
        record = {k: v for k, v in case.items() if k not in ('wave', 'expected_sha256')}
        record.update(waveform=str(wave), windows=[])
        cap = case['target_mhz']*spec['calibration_error_ppm']*1e-6
        for start in starts:
            metric = measure(wave, start, 80, 1.8, min_periods=3)
            chosen = [t for t in edges if Decimal(start)*Decimal('1e-9') <= t <= Decimal('80e-9')]
            assert len(chosen) == metric['periods']+1
            middle = (len(chosen)-1)//2
            with localcontext() as context:
                context.prec = 40
                frequency = Decimal(len(chosen)-1)/(chosen[-1]-chosen[0])*Decimal('1e-6')
                first = Decimal(middle)/(chosen[middle]-chosen[0])*Decimal('1e-6')
                last = Decimal(len(chosen)-1-middle)/(chosen[-1]-chosen[middle])*Decimal('1e-6')
            assert abs(float(frequency)-metric['mhz']) < 1e-8
            assert abs(float(abs(first-last))-metric['half_window_difference_mhz']) < 1e-8
            record['windows'].append(dict(start_ns=start, stop_ns=80, **metric,
                half_period_counts=[middle, len(chosen)-1-middle],
                independent_decimal_frequency_mhz=str(frequency),
                necessary_100ppm_cap_mhz=cap,
                half_window_drift_below_100ppm_cap=metric['half_window_difference_mhz'] <= cap))
        records.append(record)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, artifacts={}, records=records,
        predeclared_measurement_starts_ns=starts, native_jobs_added=0,
        independent_decimal_measurement_checks=len(records)*len(starts),
        measurement_window_adopted=False, calibration_model_qualified=False,
        release_qualified=False, scope=__doc__))
    print(f'Audited {len(records)} completed waveforms across {len(starts)} fixed windows', flush=True)


if __name__ == '__main__':
    main()
