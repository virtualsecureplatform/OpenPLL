#!/usr/bin/env python3
"""Route isolated load-bank candidates, then screen exact extracted circuits.

Every native check is bounded by 12h; no automatic identical retries. Range
screens select experiments only, never a release or calibrated timing model.
Run inside the release container with its devshell bin directory on PATH.
"""
import argparse
import concurrent.futures
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from dco_calibration import measure
from check_dco_c1_fine_load import check
from prepare_dco_c1_fine_load import BASE, SOURCE, BASE_SHA

PDK = '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
TAG = 'c1fine_range_001'
TIMEOUT = 43200


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def viable(values):
    return len(values) == 3 and values[0] <= 390 and values[2] >= 460 and values[0] < values[1] < values[2]


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', type=Path, required=True)
    a = p.parse_args()
    out = a.experiment.resolve()
    if (out/'plan.json').exists():
        p.error('fresh experiment required; no resume/retry')
    manifest = json.loads((out/'candidates.json').read_text())
    assert sha(SOURCE) == BASE_SHA
    spec_path = ROOT/'verification/release_requirements.json'
    spec = json.loads(spec_path.read_text())
    assert spec['voltages'] == [1.8]
    pinned = [Path(__file__), ROOT/'verification/timing450/check_dco_c1_fine_load.py',
              ROOT/'verification/timing450/prepare_dco_c1_fine_load.py', SOURCE,
              ROOT/'sky130/sky130_fd_sc_hd_pll_blackbox.v', spec_path,
              ROOT/'scripts/spice_dco_postlayout.py', ROOT/'scripts/dco_calibration.py',
              ROOT/'scripts/pll_verification.py', ROOT/'scripts/magic_full_rcx.py',
              ROOT/'scripts/reduce_spice_resistors.py', out/'candidates.json']
    for c in manifest['candidates']:
        assert sha(ROOT/c['source']) == c['source_sha256']
        pinned += [ROOT/c['source']]
        pinned += list((ROOT/'openlane'/c['top']).glob('*.*'))
        pinned += [out/(c['top']+'.json'), out/(c['top']+'.structural.json')]
    pins = {str(path):sha(path) for path in pinned}
    save(out/'plan.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
        candidates=manifest['candidates'], sha256=pins, per_check_timeout_s=TIMEOUT,
        automatic_retry=False, workers=4, range_screen=dict(corner='tt', supply_v=1.8,
        temperature_c=27, coarse=1, fine=[8,128,247], duration_ns=80,
        measurement_ns=[20,80], print_and_max_step_ps=10, reltol=1e-5, abstol=1e-9,
        acceptance='f8 <=390MHz; f247 >=460MHz; f8 < f128 < f247'),
        selection='Smallest passing bank; no adoption. All-five-mode/15PVT range screen must precede calibration.',
        physical_order='Route/extract all isolated candidates before range measurement; include routing effects in selection.',
        release_qualified=False))
    lock = threading.Lock()
    states = {}

    def update(label, **fields):
        with lock:
            states.setdefault(label, {}).update(fields)
            save(out/'status.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                stages=states, per_check_timeout_s=TIMEOUT, automatic_retry=False,
                release_qualified=False, selected=False))

    def verify_inputs():
        for path, digest in pins.items():
            if sha(path) != digest:
                raise ValueError('pinned input changed: '+path)

    def run(label, argv, cwd=ROOT):
        verify_inputs()
        update(label, state='running', argv=list(map(str,argv)))
        with (out/(label+'.log')).open('w') as log:
            child = subprocess.Popen(list(map(str,argv)), cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            # Whole process group is terminated on budget expiry, including tools.
            import os
            import signal
            deadline = __import__('time').monotonic()+TIMEOUT
            while True:
                try:
                    code = child.wait(timeout=30)
                    update(label, state='complete' if code == 0 else 'nonpass', exit_code=code)
                    return code == 0
                except subprocess.TimeoutExpired:
                    if __import__('time').monotonic() >= deadline:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()
                        update(label, state='timeout_inconclusive', automatic_retry=False)
                        return False
                    update(label, state='running', pid=child.pid)

    def physical(c):
        n, top = c['extra_loads'], c['top']
        if not run(f'route_{n}', ['librelane','--manual-pdk','--pdk-root',PDK,
                '--run-tag',TAG,'--jobs','4','--condensed',ROOT/'openlane'/top/'config.json']):
            return None
        directory = ROOT/'openlane'/top/'runs'/TAG
        gds = directory/'final/gds'/(top+'.gds')
        if not gds.exists():
            raise ValueError('missing routed GDS: '+str(gds))
        rc = out/f'rcx_{n}'
        if not run(f'extract_{n}', [sys.executable,ROOT/'scripts/magic_full_rcx.py',
                '--gds',gds,'--design',top,'--pdk',PDK+'/sky130A','--output',rc]):
            return None
        reduced = rc/(top+'.reduced.spice')
        if not run(f'reduce_{n}', [sys.executable,ROOT/'scripts/reduce_spice_resistors.py',
                                 rc/(top+'.rcx.spice'),reduced]):
            return None
        save(out/f'physical_{n}.json', dict(gds=str(gds), gds_sha256=sha(gds),
             rcx=str(reduced), rcx_sha256=sha(reduced), route_completed=True,
             release_qualified=False, scope='Experimental route/extraction; later physical qualification remains required.'))
        return c, reduced

    # No simulator starts until routing/extraction finishes, keeping resource
    # use bounded independently of LibreLane's worker count.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        physical_results = list(pool.map(physical, manifest['candidates']))
    viable_candidates = []
    for result in physical_results:
        if result is None:
            continue
        c, rc = result
        n = c['extra_loads']
        label = f'tt_screen_{n}'
        directory = out/label
        argv = [sys.executable, ROOT/'scripts/spice_dco_postlayout.py',
                '--simulator','xyce','--xyce','/opt/xyce/bin/Xyce -linsolv KLU',
                '--pdk-root',PDK,'--rcx-netlist',rc,'--subckt-name',c['top'],
                '--coarse-codes','1','--codes','8,128,247','--corner','tt',
                '--vdd','1.8','--temperature-c','27','--sim-time-ns','80',
                '--meas-start-ns','20','--step-ps','10','--max-step-ps','10',
                '--xyce-reltol','1e-5','--xyce-abstol','1e-9',
                '--timeout-s',str(TIMEOUT),'--jobs','3','--build-dir',directory]
        ok = run(label,argv)
        csvfile = directory/'dco_postlayout_results.csv'
        rows = list(csv.DictReader(csvfile.open())) if csvfile.exists() else []
        metrics = []
        if ok and len(rows) == 3 and all(row['status']=='pass' for row in rows):
            for row in sorted(rows,key=lambda r:int(r['code'])):
                wave = Path(row['waveform'])
                metrics.append(dict(code=int(row['code']), waveform=str(wave),
                                    waveform_sha256=sha(wave), **measure(wave,20,80,1.8,min_periods=3)))
        passed = viable([m['mhz'] for m in metrics])
        save(out/f'screen_{n}.json', dict(points=metrics, screen_passed=passed,
             native_complete=ok, calibration_qualified=False, release_qualified=False))
        update(label, state='screen_pass' if passed else 'screen_nonpass', points=metrics)
        if passed:
            viable_candidates.append(n)
    winner = min(viable_candidates) if viable_candidates else None
    save(out/'decision.json',dict(candidate_for_pvt_screen=winner,
        viable_load_counts=viable_candidates, selected=False, release_qualified=False,
        state='PVT_RANGE_SCREEN_REQUIRED' if winner else 'NO_VIABLE_CANDIDATE',
        next_gate='All five target modes at each of 15 nominal-voltage PVT points; then adjacent-code/convergence and affected physical/interface qualification.'))
    update('decision', state='PVT_RANGE_SCREEN_REQUIRED' if winner else 'NO_VIABLE_CANDIDATE',
           candidate_for_pvt_screen=winner)


if __name__ == '__main__':
    main()
