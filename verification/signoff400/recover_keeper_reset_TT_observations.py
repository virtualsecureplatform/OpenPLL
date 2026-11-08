"""Recover the completed TT capture after the specific result-dictionary failure."""
import json
from pathlib import Path
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity
from run_keeper_reset_pulse_grid_v3 import assess


def run():
    source = ROOT / 'build/signoff400/selected_keeper_reset_pulse_grid_1504'
    output = ROOT / 'build/signoff400/selected_keeper_reset_TT_observations_1508'
    output.mkdir(parents=True, exist_ok=False)
    launch = ROOT / 'verification/prototype400/selected_keeper_reset_pulse_grid_launch_1504.json'
    a = json.loads(launch.read_text())
    verify(a['input_sha256'])
    for name in ('owner.json', 'tt/native.process.json'):
        process = json.loads((source / name).read_text())
        if identity(process['pid']) == process['birth']:
            raise ValueError('completed original capture required')
    status = json.loads((source / 'status.json').read_text())
    if status['reason'] != 'TypeError("dict() got multiple values for keyword argument \'negative_control\'")':
        raise ValueError('only known post-native failure accepted')
    log = (source / 'tt/native.log').read_text()
    if 'ngspice-47 done' not in log or 'No. of Data Rows :' not in log:
        raise ValueError('normal native completion markers required')
    files = [launch, Path(__file__).resolve(), Path(__file__).with_name('run_keeper_reset_pulse_grid_v3.py'),
             *[source / n for n in ('owner.json','status.json','plan.json','cells.spice',
                 'tt/native.process.json','tt/native.log','tt/reset.cir','tt/.spiceinit','tt/waveform.dat')]]
    pins = {str(p): sha(p) for p in files}
    cases = json.loads((source / 'plan.json').read_text())['cases']
    data = source / 'tt/waveform.dat'
    expected = ['time'] + [f'v(q{i})' for i in range(len(cases))] + [f'v(ctrl{i})' for i in range(len(cases))]
    if data.open().readline().split() != expected:
        raise ValueError('exact saved columns required')
    values = np.loadtxt(data, skiprows=1)
    rows = [dict(corner='tt', **{**c, **assess(values[:,0], values[:,i+1],
            values[:,len(cases)+i+1], c['reset_state'], c['negative_control'])})
            for i,c in enumerate(cases)]
    detail = output / 'observations.json'
    save(detail, rows)
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail):sha(detail)},
         native_TT_completed_before_collector_failure=True, native_rerun=False, cases=len(rows),
         failed_cases=sum(not r['fixture_passed'] for r in rows),
         all_grid_fixtures_pass=all(r['fixture_passed'] for r in rows),
         minimum_pulse_bound_qualified=False, routed_reset_timing_qualified=False, release_ready=False))
    save(output / 'status.json', dict(state='completed_TT_observations_recovered', release_ready=False))


if __name__ == '__main__':
    run()
