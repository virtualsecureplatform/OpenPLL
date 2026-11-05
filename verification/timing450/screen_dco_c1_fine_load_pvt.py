#!/usr/bin/env python3
"""Follow the TT decision with measured five-mode nominal-PVT range screening.

Conservative gate: a missing measured endpoint bracket rejects the experiment
for this screen. It does not prove global unreachability or interpolation.
Never starts calibration, changes a release model, or retries an identical run.
"""
import argparse
import concurrent.futures
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from run_dco_c1_fine_load import ROOT, PDK, TIMEOUT, sha, save
sys.path.insert(0, str(ROOT/'scripts'))
from dco_calibration import measure


def find_bracket(target, sample):
    """Use coarse monotonicity only as a search heuristic; require measurements."""
    low, high = 0, 47
    coarse = {100:13,250:4,300:3,400:1,450:1}[target]
    trace = []
    while low <= high:
        values = sample(coarse)
        trace.append(dict(coarse=coarse, endpoints_mhz=values))
        if values is None:
            return dict(passed=False, reason='native_nonpass', trace=trace)
        left, right = values
        if not left < right:
            return dict(passed=False, reason='sampled_fine_order_failed', trace=trace)
        if left <= target <= right:
            return dict(passed=True, coarse=coarse, endpoints_mhz=values, trace=trace)
        if right < target:
            high = coarse-1
        else:
            low = coarse+1
        # Check the nearest band first; subsequently bisect the remaining range.
        neighbor = coarse-1 if right < target else coarse+1
        coarse = neighbor if len(trace) == 1 and low <= neighbor <= high else (low+high)//2
    return dict(passed=False, reason='no_measured_bracket_in_adaptive_search', trace=trace,
                global_unreachability_proven=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    a = parser.parse_args()
    experiment = a.experiment.resolve()
    out = experiment/'pvt_range'
    out.mkdir(exist_ok=False)
    lock = threading.Lock()
    states = {}

    def update(label, **fields):
        with lock:
            states.setdefault(label, {}).update(fields)
            save(out/'status.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                stages=states, release_qualified=False, automatic_retry=False,
                per_native_timeout_s=TIMEOUT))

    update('dependency', state='waiting_for_tt_screen')
    while not (experiment/'decision.json').exists():
        launch = json.loads((experiment/'launch.json').read_text())
        try:
            os.kill(launch['pid'],0)
        except ProcessLookupError:
            update('dependency', state='controller_ended_without_decision')
            return
        time.sleep(10)
    decision = json.loads((experiment/'decision.json').read_text())
    if not decision['viable_load_counts']:
        update('dependency', state='NO_VIABLE_TT_CANDIDATE')
        return
    specpath = ROOT/'verification/release_requirements.json'
    spec = json.loads(specpath.read_text())
    assert spec['voltages'] == [1.8]
    pins = {str(specpath):sha(specpath), str(Path(__file__).resolve()):sha(__file__),
            str(ROOT/'scripts/spice_dco_postlayout.py'):sha(ROOT/'scripts/spice_dco_postlayout.py'),
            str(ROOT/'scripts/dco_calibration.py'):sha(ROOT/'scripts/dco_calibration.py')}
    pins.update(json.loads((experiment/'plan.json').read_text())['sha256'])
    pins[str(experiment/'decision.json')] = sha(experiment/'decision.json')
    save(out/'plan.json', dict(candidates=sorted(decision['viable_load_counts']), sha256=pins,
        supply_v=1.8, corners=spec['corners'], temperatures_c=spec['temperatures_c'],
        modes_mhz=spec['modes_mhz'], max_native_workers=4, per_native_timeout_s=TIMEOUT,
        automatic_retry=False, release_qualified=False,
        acceptance='Each mode must have a measured ordered fine8/fine247 bracket in one band. Short screens do not qualify interior tuning or convergence.',
        reject_policy='Stop a candidate at first PVT point lacking a bracket; preserve all artifacts. Try the next TT-viable load count.',
        next_gate='If all75 measured brackets pass: measured fine-code search, adjacent-code numerical/settling qualification, model validation and affected physical/interface checks.'))

    def verify():
        for path,digest in pins.items():
            if sha(path) != digest:
                raise ValueError('pinned source changed: '+path)

    candidates = {c['extra_loads']:c for c in json.loads((experiment/'candidates.json').read_text())['candidates']}

    def point(count, corner, temp):
        label = f'n{count}_{corner}_{temp}'
        cache = {}
        update(label, state='running', modes={})
        physical = json.loads((experiment/f'physical_{count}.json').read_text())
        rc = Path(physical['rcx'])
        assert sha(rc) == physical['rcx_sha256']
        c = candidates[count]
        if corner == 'tt' and temp == 27:
            metrics = json.loads((experiment/f'screen_{count}.json').read_text())['points']
            cache[1] = [next(m['mhz'] for m in metrics if m['code']==code) for code in (8,247)]

        def sample(coarse):
            if coarse in cache:
                return cache[coarse]
            verify()
            assert sha(rc) == physical['rcx_sha256']
            directory = out/f'{label}_c{coarse}'
            assert not directory.exists(), 'identical retry prohibited'
            argv = [sys.executable,ROOT/'scripts/spice_dco_postlayout.py',
                '--simulator','xyce','--xyce','/opt/xyce/bin/Xyce -linsolv KLU',
                '--pdk-root',PDK,'--rcx-netlist',rc,'--subckt-name',c['top'],
                '--coarse-codes',str(coarse),'--codes','8,247','--corner',corner,
                '--vdd','1.8','--temperature-c',str(temp),'--sim-time-ns','80',
                '--meas-start-ns','20','--step-ps','10','--max-step-ps','10',
                '--xyce-reltol','1e-5','--xyce-abstol','1e-9',
                '--timeout-s',str(TIMEOUT),'--jobs','2','--build-dir',directory]
            with (out/f'{label}_c{coarse}.log').open('x') as log:
                child = subprocess.Popen(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                deadline = time.monotonic()+TIMEOUT
                while True:
                    try:
                        code = child.wait(timeout=30)
                        break
                    except subprocess.TimeoutExpired:
                        update(label,state='running',current_coarse=coarse,engine_pid=child.pid)
                        if time.monotonic() >= deadline:
                            os.killpg(child.pid,signal.SIGTERM)
                            try:
                                child.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid,signal.SIGKILL)
                                child.wait()
                            save(out/f'{label}_c{coarse}.timeout.json',dict(state='timeout_inconclusive', automatic_retry=False))
                            cache[coarse] = None
                            return None
            csvfile = directory/'dco_postlayout_results.csv'
            rows = list(csv.DictReader(csvfile.open())) if csvfile.exists() else []
            if code or len(rows)!=2 or any(r['status']!='pass' for r in rows):
                cache[coarse] = None
                return None
            metrics = []
            for row in sorted(rows,key=lambda r:int(r['code'])):
                wave = Path(row['waveform'])
                metrics.append(dict(code=int(row['code']),waveform=str(wave),waveform_sha256=sha(wave),
                                    **measure(wave,20,80,1.8,min_periods=3)))
            save(out/f'{label}_c{coarse}.measurements.json',dict(points=metrics,release_qualified=False))
            cache[coarse] = [m['mhz'] for m in metrics]
            return cache[coarse]

        modes = {}
        # Check the repaired modes first, then the other three retained modes.
        for target in (450,400,300,250,100):
            modes[str(target)] = find_bracket(target,sample)
            update(label, state='running', modes=modes)
            if not modes[str(target)]['passed']:
                break
        passed = len(modes)==5 and all(m['passed'] for m in modes.values())
        result = dict(corner=corner,temperature_c=temp,supply_v=1.8,modes=modes,passed=passed,
                      release_qualified=False,calibration_qualified=False)
        save(out/f'{label}.json',result)
        update(label,state='range_pass' if passed else 'range_nonpass',modes=modes)
        return result

    points = [('tt',27)]+[(corner,temp) for corner in spec['corners'] for temp in spec['temperatures_c'] if (corner,temp)!=('tt',27)]
    winner = None
    for count in sorted(decision['viable_load_counts']):
        # TT first, so another missing nominal mode cannot launch a full matrix.
        results = [point(count,*points[0])]
        if results[0]['passed']:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                for i in range(1,len(points),2):
                    batch = list(pool.map(lambda pt:point(count,*pt), points[i:i+2]))
                    results.extend(batch)
                    if any(not r['passed'] for r in batch):
                        break
        passed = len(results)==15 and all(r['passed'] for r in results)
        save(out/f'candidate_{count}.json',dict(points=results,range_screen_passed=passed,
            measured_mode_brackets=sum(sum(m['passed'] for m in r['modes'].values()) for r in results),
            calibration_qualified=False,release_qualified=False))
        if passed:
            winner = count
            break
    save(out/'decision.json',dict(candidate_for_calibration=winner,selected=False,release_qualified=False,
        state='CALIBRATION_AND_INTERFACE_QUALIFICATION_REQUIRED' if winner else 'NO_CANDIDATE_PASSED_RANGE_SCREEN',
        global_unreachability_proven=False))
    update('decision',state='CALIBRATION_AND_INTERFACE_QUALIFICATION_REQUIRED' if winner else 'NO_CANDIDATE_PASSED_RANGE_SCREEN',candidate_for_calibration=winner)


if __name__ == '__main__':
    main()
