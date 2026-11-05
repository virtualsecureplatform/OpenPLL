#!/usr/bin/env python3
"""Review fixed windows of explicit completed native DCO results.

Window drift below 100ppm is only necessary. Local LSB, duration, timestep,
tolerance, loaded interfaces and model-domain enclosure remain separate.
"""
import argparse
import json
from pathlib import Path
import signal

from audit_dco_settling_windows import independent_edges
from run_dco_duration_probe_v3 import decimal_measure
from run_dco_qualification import REQUIREMENTS,measure,sha,save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',required=True,type=Path,action='append')
    parser.add_argument('--target-mhz',required=True,type=int)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('12h review budget')))
    signal.alarm(43200)
    spec = json.loads(REQUIREMENTS.read_text())
    assert args.target_mhz in spec['modes_mhz']
    assert spec['calibration_error_ppm'] == 100
    files = [Path(__file__).resolve(),REQUIREMENTS,
        Path(__file__).with_name('audit_dco_settling_windows.py'),
        Path(__file__).with_name('run_dco_duration_probe_v3.py'),
        Path(__file__).with_name('run_dco_qualification.py'),
        Path(__file__).resolve().parents[2]/'scripts/dco_calibration.py']
    pins = {str(p):sha(p) for p in files}
    cases = []
    for path in args.result:
        path = path.resolve()
        data = json.loads(path.read_text())
        assert data['state'] == 'native_pass'
        wave = Path(data['metric']['waveform'])
        assert sha(wave) == data['metric']['waveform_sha256']
        provenance = wave.with_suffix('.provenance.json')
        receipt = json.loads(provenance.read_text())
        assert receipt['completed'] and receipt['parameters']['sim_time_ns'] == 80
        assert receipt['parameters']['vdd'] == 1.8
        for file,digest in receipt['files'].items():
            assert file not in pins or pins[file] == digest
            pins[file] = digest
        for file in (path,wave,provenance):
            pins[str(file)] = sha(file)
        cases.append((wave,receipt['parameters']))
    # Verify shared PDK inputs once across cases, without touching live outputs.
    for path,digest in pins.items():
        assert sha(path) == digest,path
    rows = []
    for wave,parameters in cases:
        edges = independent_edges(wave)
        windows = []
        for start in (20,30,40,50,60):
            metric = measure(wave,start,80,1.8,min_periods=3)
            frequency,drift = decimal_measure(edges,start,80)
            assert abs(float(frequency)-metric['mhz']) < 1e-8
            assert abs(float(drift)-metric['half_window_difference_mhz']) < 1e-8
            cap = args.target_mhz*100e-6
            windows.append(dict(start_ns=start,stop_ns=80,**metric,
                independent_decimal_frequency_mhz=str(frequency),
                independent_decimal_half_window_difference_mhz=str(drift),
                necessary_100ppm_cap_mhz=cap,half_window_drift_below_100ppm_cap=float(drift)<=cap))
        rows.append(dict(waveform=str(wave),parameters=parameters,windows=windows))
    for wave,_ in cases:
        assert sha(wave) == pins[str(wave)]
    out = args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={},records=rows,
        target_mhz=args.target_mhz,predeclared_measurement_starts_ns=[20,30,40,50,60],
        independent_decimal_checks=len(rows)*5,native_jobs_added=0,
        measurement_window_adopted=False,calibration_model_qualified=False,
        physical_loaded_model_qualified=False,release_qualified=False,scope=__doc__))
    print(json.dumps([dict(code=row['parameters']['code'],drifts_mhz=[w['half_window_difference_mhz'] for w in row['windows']]) for row in rows]))


if __name__ == '__main__':
    main()
