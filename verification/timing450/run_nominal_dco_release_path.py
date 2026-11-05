#!/usr/bin/env python3
"""Measure nominal candidate bands, then test one local calibration hypothesis.

No short screen is promoted to a calibration model. Each native invocation has
a 12h timeout. Failed/timed-out checks are retained and never retried here.
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
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from dco_calibration import measure, assess

RCX = ROOT / 'build/modern_25mhz/v5_turn10_boost8_osc8_load36_all_net_rc/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36.reduced.spice'
RCX_SHA = '704cce5be85c7e91165bf017f79ccefbfd0dec35581c5965646fc2c946c7b9d4'
SUBCKT = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36'
PDK = '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def choose_band(points, target, low=8, high=247):
    """Return an interpolated *search seed*, never a qualified tuning model."""
    candidates = []
    for coarse in sorted({c for c, code in points}):
        if (coarse, low) not in points or (coarse, high) not in points:
            continue
        left, right = points[coarse, low], points[coarse, high]
        if left < target < right:
            seed = round(low + (high-low)*(target-left)/(right-left))
            seed = max(low+1, min(high-1, seed))
            candidates.append((min(target-left, right-target), coarse, seed))
    if not candidates:
        return None
    _, coarse, seed = max(candidates)
    return coarse, seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists()
    specpath = ROOT / 'verification/release_requirements.json'
    spec = json.loads(specpath.read_text())
    assert spec['voltages'] == [1.8] and 450 in spec['modes_mhz']
    assert sha(RCX) == RCX_SHA
    sources = [specpath, RCX, Path(__file__).resolve(),
               ROOT/'scripts/dco_calibration.py', ROOT/'scripts/spice_dco_postlayout.py',
               ROOT/'scripts/pll_verification.py']
    pins = {str(path):sha(path) for path in sources}
    output.mkdir(parents=True)
    plan = {'observed_utc': datetime.now(timezone.utc).isoformat(),
            'supply_v':1.8, 'corner':'tt', 'temperature_c':27, 'target_mhz':450,
            'screen':{'coarse':[0,1,16], 'codes':[8,247], 'duration_ns':80,
                      'measure_start_ns':20, 'max_step_ps':10, 'workers':4},
            'next_step':'Only if screened endpoints bracket450MHz, measure a local seed plus both adjacent codes under four separate numerical/duration variants.',
            'per_native_timeout_seconds':43200, 'automatic_retry':False,
            'sha256':pins, 'release_qualified':False,
            'scope':'One nominal TT27 search and local convergence experiment. No full fine-code interpolation,15PVT, five-mode acquisition, physical noise or release claim.'}
    save(output/'plan.json', plan)
    if args.prepare_only:
        print(json.dumps({k:v for k,v in plan.items() if k!='sha256'}), flush=True)
        return
    lock = threading.Lock()
    states = {}

    def update(label, **fields):
        with lock:
            states.setdefault(label, {}).update(fields)
            save(output/'status.json', {'observed_utc':datetime.now(timezone.utc).isoformat(),
                 'stages':states, 'supply_v':1.8, 'per_native_timeout_seconds':43200,
                 'release_qualified':False})

    def run(label, coarse, codes, stop, start, step, reltol, abstol, workers):
        for path, digest in pins.items():
            assert sha(path) == digest, path
        directory = output/label
        assert not directory.exists()
        argv = [sys.executable, str(ROOT/'scripts/spice_dco_postlayout.py'),
                '--simulator','xyce','--xyce','/opt/xyce/bin/Xyce -linsolv KLU',
                '--pdk-root',PDK,'--rcx-netlist',str(RCX),'--subckt-name',SUBCKT,
                '--coarse-codes',','.join(map(str,coarse)), '--codes',','.join(map(str,codes)),
                '--corner','tt','--vdd','1.8','--temperature-c','27',
                '--sim-time-ns',str(stop),'--meas-start-ns',str(start),
                '--step-ps',str(step),'--max-step-ps',str(step),
                '--xyce-reltol',str(reltol),'--xyce-abstol',str(abstol),
                '--timeout-s','43200','--jobs',str(workers),'--build-dir',str(directory)]
        update(label, state='validating_inputs', argv=argv)
        with (output/(label+'.log')).open('w') as stream:
            child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
            while True:
                try:
                    code = child.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    sidecars = list(directory.glob('dco_*.provenance.json'))
                    completed = 0
                    for sidecar in sidecars:
                        try:
                            completed += bool(json.loads(sidecar.read_text()).get('completed',False))
                        except json.JSONDecodeError:
                            # Legacy writers replace these sidecars in place.
                            pass
                    update(label, state='running', controller_pid=child.pid,
                           native_completed=completed, native_requested=len(coarse)*len(codes))
        result = directory/'dco_postlayout_results.csv'
        rows = list(csv.DictReader(result.open())) if result.exists() else []
        passed = code == 0 and len(rows)==len(coarse)*len(codes) and all(row['status']=='pass' for row in rows)
        update(label, state='complete' if passed else 'nonpass', exit_code=code,
               native_requested=len(coarse)*len(codes),
               native_passing=sum(row['status']=='pass' for row in rows),
               native_timeouts=sum(row['timed_out']=='yes' for row in rows))
        return passed, directory, rows

    passed, directory, rows = run('screen',[0,1,16],[8,247],80,20,10,1e-5,1e-9,4)
    if not passed:
        update('decision', state='blocked_screen_nonpass', automatic_retry=False)
        return
    # Use full late windows, not the engine's first-two-period summary.
    points = {}
    metrics = []
    for row in rows:
        wave = Path(row['waveform'])
        try:
            metric = measure(wave,20,80,1.8,min_periods=3)
        except ValueError as error:
            update('decision', state='insufficient_screen_measurement',
                   waveform=str(wave), reason=str(error), automatic_retry=False)
            return
        key = int(row['coarse_code']),int(row['code'])
        points[key] = metric['mhz']
        metrics.append({'coarse':key[0],'code':key[1],**metric,
                        'waveform':str(wave),'waveform_sha256':sha(wave)})
    selected = choose_band(points,450)
    save(output/'screen_measurements.json', {'points':metrics, 'selected_band_and_seed':selected,
         'calibration_qualified':False,'release_qualified':False,
         'scope':'Endpoints choose a search seed only; unsettled/interpolated values cannot qualify a model.'})
    if selected is None:
        update('decision', state='no_screened_band_brackets_target',
               next_action='Inspect measured bands and extend only the necessary coarse search; no extrapolated model.')
        return
    coarse, seed = selected
    codes = [seed-1,seed,seed+1]
    update('decision', state='local_convergence_running', coarse=coarse, codes=codes)
    settings = {'baseline':(80,20,10,1e-5,1e-9),
                'step':(80,20,5,1e-5,1e-9),
                'tolerance':(80,20,10,1e-6,1e-10),
                'settling':(160,40,5,1e-5,1e-9)}
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {label:pool.submit(run,label,[coarse],codes,*values,1)
                   for label,values in settings.items()}
        for label,future in futures.items():
            results[label] = future.result()
    if not all(value[0] for value in results.values()):
        update('decision', state='blocked_local_variant_nonpass', automatic_retry=False)
        return
    samples = {}
    for label,(passed,directory,rows) in results.items():
        stop,start,*_ = settings[label]
        samples[label] = {int(row['code']):measure(Path(row['waveform']),start,stop,1.8)
                          for row in rows}
    result = assess(samples,450,spec)
    result.update(coarse=coarse, seed=seed, supply_v=1.8, corner='tt', temperature_c=27,
                  variants=samples, calibration_model_qualified=False, release_qualified=False,
                  scope='Three-code local numerical convergence only. No full-band interpolation, global settling bound, wholePLL or release qualification.')
    save(output/'local_convergence.json',result)
    update('decision', state='local_convergence_pass' if result['convergence_passed'] else 'local_convergence_fail',
           next_action='Inspect drift and variant agreement before extending the calibration model; no automatic identical retry.')


if __name__=='__main__':
    main()
