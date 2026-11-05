#!/usr/bin/env python3
"""Four-mode range gates and local convergence, with a shared native budget.

One engine runs one native check. Pending engines reserve slots, so preparation
cannot oversubscribe surviving legacy Xyce processes. No resume or identical
automatic retry; short screens never become a calibrated model.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'verification/timing450'))
from dco_calibration import measure, assess
from enforce_native_check_budget import process as native_process
from screen_dco_c1_fine_load_pvt import find_bracket

REQUIREMENTS = ROOT/'verification/release_requirements_400mhz.json'
OLD = ROOT/'build/timing450/dco_c1_fine_load_001'
PDK = '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
BUDGET = 43200
VARIANTS = {'baseline':(80,20,10,1e-5,1e-9),
            'step':(80,20,5,1e-5,1e-9),
            'tolerance':(80,20,10,1e-6,1e-10),
            'settling':(160,40,10,1e-5,1e-9)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def validate_spec(spec):
    if spec['modes_mhz'] != [100,250,300,400] or spec['reference_mhz'] != 25:
        raise ValueError('four-mode400MHz requirements required')
    if spec['voltages'] != [1.8] or len(spec['corners'])*len(spec['temperatures_c']) != 15:
        raise ValueError('nominal15PVT scope required')
    if spec['release_scope']['required_mode_pvt_combinations'] != 60:
        raise ValueError('stale release matrix')


def occupancy(reservations, native):
    # Engines preparing decks reserve slots even before Xyce starts. Count
    # their children through the reservation, and other native jobs directly.
    parents = {pid for pid in reservations.values() if pid is not None}
    return len(reservations) + sum(item['ppid'] not in parents for item in native)


def covered(results, spec):
    expected = {(c,t) for c in spec['corners'] for t in spec['temperatures_c']}
    actual = {(r['corner'],r['temperature_c']) for r in results}
    return (len(results)==len(expected) and actual==expected and
            all(set(r['modes']) == {str(m) for m in spec['modes_mhz']} and
                all(v['passed'] for v in r['modes'].values()) for r in results))


def seed_from_bracket(target, result):
    left,right = result['endpoints_mhz']
    if not left <= target <= right or not left < right:
        raise ValueError('measured ordered bracket required')
    # Search hint only; no interpolated operating point or model claim.
    return max(9,min(246,round(8+(247-8)*(target-left)/(right-left))))


class Controller:
    def __init__(self, output):
        self.output = output
        output.mkdir(parents=True,exist_ok=False)
        self.spec = json.loads(REQUIREMENTS.read_text())
        validate_spec(self.spec)
        self.lock = threading.RLock()
        self.reservations = {}
        self.states = {}
        self.cache = {}
        self.pins = {}
        reuse_pins = {}
        self.stopping = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.candidates = {c['extra_loads']:c for c in json.loads((OLD/'candidates.json').read_text())['candidates']}
        inputs = [REQUIREMENTS,Path(__file__),ROOT/'verification/release_plan_400mhz.json',
                  ROOT/'sky130/release_400mhz_targets.json',ROOT/'scripts/spice_dco_postlayout.py',
                  ROOT/'scripts/dco_calibration.py',ROOT/'scripts/pll_verification.py',
                  ROOT/'scripts/xyce_utils.py',ROOT/'verification/timing450/enforce_native_check_budget.py',
                  ROOT/'verification/timing450/screen_dco_c1_fine_load_pvt.py',
                  ROOT/'verification/timing450/run_dco_c1_fine_load.py',
                  ROOT/'verification/timing450/check_dco_c1_fine_load.py',
                  ROOT/'verification/timing450/prepare_dco_c1_fine_load.py',OLD/'candidates.json']
        for count in (160,144):
            physical_path = OLD/f'physical_{count}.json'
            physical = json.loads(physical_path.read_text())
            self.candidates[count]['rcx'] = physical['rcx']
            for key in ('gds','rcx'):
                assert sha(physical[key]) == physical[key+'_sha256']
            c = self.candidates[count]
            assert sha(ROOT/c['source']) == c['source_sha256']
            inputs += [physical_path,Path(physical['rcx']),Path(physical['gds']),ROOT/c['source'],OLD/f'screen_{count}.json']
            screen = json.loads((OLD/f'screen_{count}.json').read_text())
            assert screen['native_complete']
            for item in screen['points']:
                wave = Path(item['waveform'])
                assert sha(wave) == item['waveform_sha256']
                side = wave.with_suffix('.provenance.json')
                provenance = json.loads(side.read_text())
                assert provenance['completed']
                param = provenance['parameters']
                assert param['subckt_name'] == c['top'] and param['corner']=='tt'
                assert param['vdd']==1.8 and param['temperature_c']==27
                assert param['sim_time_ns']==80 and param['meas_start_ns']==20
                assert param['max_step_ps']==10 and param['therm_invert']
                assert Path(param['rcx_netlist']).resolve()==Path(c['rcx']).resolve()
                for path,digest in provenance['files'].items():
                    if path in reuse_pins and reuse_pins[path]!=digest:
                        raise ValueError('inconsistent reused input: '+path)
                    reuse_pins[path]=digest
                deck = wave.with_suffix('.spice')
                assert sha(deck) == provenance['netlist_sha256']
                metric = measure(wave,20,80,1.8,min_periods=3)
                assert abs(metric['mhz']-item['mhz']) < 1e-9
                self.cache[(count,'tt',27,1,item['code'],'baseline')] = dict(metric,code=item['code'],
                    waveform=str(wave),waveform_sha256=sha(wave),reused=True)
                inputs += [wave,side,deck]
        self.pins = {str(p.resolve()):sha(p) for p in inputs}
        for path,digest in reuse_pins.items():
            if path in self.pins and self.pins[path]!=digest:
                raise ValueError('reused input changed: '+path)
            self.pins[path]=digest
        self.verify()
        save(output/'plan.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
            requirements=str(REQUIREMENTS),sha256=self.pins,candidate_priority=[160,144],
            modes_mhz=self.spec['modes_mhz'],pvt_points=15,mode_pvt_cases=60,
            per_native_timeout_s=BUDGET,max_native_workers_including_legacy=4,
            measurement_minimum_periods=3,
            automatic_identical_retry=False,variants=VARIANTS,release_qualified=False,
            scope='Measured range gates then local convergence. Full model/interpolation, interfaces, timing, wholePLL and physical qualification remain mandatory.'))
        self.update('initialization',state='inputs_verified',reused_tt_points=len(self.cache))

    def verify(self):
        for path,digest in self.pins.items():
            if sha(path) != digest:
                self.stopping.set()
                raise ValueError('pinned input changed: '+path)

    def update(self, label, **fields):
        with self.lock:
            self.states.setdefault(label,{}).update(copy.deepcopy(fields))
            save(self.output/'status.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                 stages=self.states,release_qualified=False,selected=False,
                 per_native_timeout_s=BUDGET,max_native_workers=4,automatic_identical_retry=False))

    def live(self):
        found = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            item = native_process(int(entry.name),ROOT)
            if item:
                try:
                    item['ppid'] = int((entry/'stat').read_text().rsplit(')',1)[1].split()[1])
                    found.append(item)
                except (OSError,ValueError):
                    continue
        return found

    def run_case(self,count,corner,temp,coarse,code,variant='baseline'):
        key = count,corner,temp,coarse,code,variant
        if key in self.cache:
            return self.cache[key]
        label = f'n{count}_{corner}_{temp}_c{coarse}_f{code}_{variant}'
        stop,start,step,rel,ab = VARIANTS[variant]
        c = self.candidates[count]
        directory = self.output/label
        if directory.exists():
            raise ValueError('identical retry prohibited: '+label)
        self.verify()
        self.update(label,state='waiting_for_native_slot')
        while True:
            if self.stopping.is_set():
                return None
            with self.lock:
                native = self.live()
                used = occupancy(self.reservations,native)
                if used < 4:
                    self.reservations[label] = None
                    self.update('admission',state='active',reserved_and_external=used+1,
                                observed_native_checks=len(native),legacy_pids=[n['pid'] for n in native if n['ppid'] not in self.reservations.values()])
                    break
                self.update(label,state='waiting_for_native_slot',reserved_and_external=used)
            time.sleep(5)
        argv = [sys.executable,ROOT/'scripts/spice_dco_postlayout.py',
                '--simulator','xyce','--xyce','/opt/xyce/bin/Xyce -linsolv KLU',
                '--pdk-root',PDK,'--rcx-netlist',c['rcx'],'--subckt-name',c['top'],
                '--coarse-codes',str(coarse),'--codes',str(code),'--corner',corner,
                '--vdd','1.8','--temperature-c',str(temp),'--sim-time-ns',str(stop),
                '--meas-start-ns',str(start),'--step-ps',str(step),'--max-step-ps',str(step),
                '--xyce-reltol',str(rel),'--xyce-abstol',str(ab),
                '--timeout-s',str(BUDGET),'--jobs','1','--build-dir',directory]
        try:
            self.verify()
            with (self.output/(label+'.log')).open('x') as log:
                child = subprocess.Popen(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                with self.lock:
                    self.reservations[label] = child.pid
                self.update(label,state='running',engine_pid=child.pid,argv=list(map(str,argv)))
                deadline = time.monotonic()+BUDGET
                timed_out = False
                while True:
                    try:
                        result = child.wait(timeout=30)
                        break
                    except subprocess.TimeoutExpired:
                        self.update(label,state='running',engine_pid=child.pid)
                        if time.monotonic() >= deadline:
                            timed_out = True
                            os.killpg(child.pid,signal.SIGTERM)
                            try:
                                child.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid,signal.SIGKILL)
                                child.wait()
                            result = child.returncode
                            break
            csvfile = directory/'dco_postlayout_results.csv'
            rows = list(csv.DictReader(csvfile.open())) if csvfile.exists() else []
            if timed_out or result or len(rows)!=1 or rows[0]['status']!='pass':
                state = 'timeout_inconclusive' if timed_out or any(r.get('timed_out')=='yes' for r in rows) else 'native_nonpass'
                save(self.output/(label+'.result.json'),dict(state=state,release_qualified=False,automatic_retry=False))
                self.update(label,state=state,exit_code=result)
                return None
            row = rows[0]
            wave = Path(row['waveform'])
            side = json.loads(wave.with_suffix('.provenance.json').read_text())
            assert side['completed'] and int(row['code'])==code and int(row['coarse_code'])==coarse
            assert side['parameters']['corner']==corner and side['parameters']['temperature_c']==temp
            metric = dict(code=code,**measure(wave,start,stop,1.8,min_periods=3),
                          waveform=str(wave),waveform_sha256=sha(wave),reused=False)
            save(self.output/(label+'.result.json'),dict(state='native_pass',metric=metric,release_qualified=False))
            self.cache[key] = metric
            self.update(label,state='native_pass',metric=metric)
            return metric
        finally:
            with self.lock:
                self.reservations.pop(label,None)

    def point(self,count,corner,temp):
        label = f'range_n{count}_{corner}_{temp}'
        sampled = {}
        def sample(coarse):
            if coarse not in sampled:
                futures = [self.pool.submit(self.run_case,count,corner,temp,coarse,code) for code in (8,247)]
                values = [f.result() for f in futures]
                sampled[coarse] = [v['mhz'] for v in values] if all(values) else None
            return sampled[coarse]
        modes = {}
        # The400 bracket is reused at TT; other modes gate PVT expansion.
        for target in (400,300,250,100):
            modes[str(target)] = find_bracket(target,sample)
            self.update(label,state='running',modes=modes)
            if not modes[str(target)]['passed']:
                break
        result = dict(corner=corner,temperature_c=temp,modes=modes,supply_v=1.8,
                      passed=len(modes)==4 and all(m['passed'] for m in modes.values()),
                      global_unreachability_proven=False,release_qualified=False)
        save(self.output/(label+'.json'),result)
        self.update(label,state='range_pass' if result['passed'] else 'range_nonpass',modes=modes)
        return result

    def qualify_local(self,count,point,target):
        bracket = point['modes'][str(target)]
        coarse = bracket['coarse']
        seed = seed_from_bracket(target,bracket)
        # Bounded measured binary search. Interpolation is only the first hint.
        low,high = 8,247
        for _ in range(9):
            metric = self.run_case(count,point['corner'],point['temperature_c'],coarse,seed)
            if metric is None:
                return False
            ppm = target*self.spec['frequency_error_ppm']*1e-6
            if abs(metric['mhz']-target)<=ppm:
                break
            if metric['mhz'] < target:
                low = seed+1
            else:
                high = seed-1
            if low>high:
                return False
            seed = (low+high)//2
        if not 9 <= seed <= 246 or abs(metric['mhz']-target)>ppm:
            return False
        codes = [seed-1,seed,seed+1]
        tasks = {(variant,code):self.pool.submit(self.run_case,count,point['corner'],point['temperature_c'],coarse,code,variant)
                 for variant in VARIANTS for code in codes}
        samples = {variant:{} for variant in VARIANTS}
        for (variant,code),future in tasks.items():
            value = future.result()
            if value is None:
                return False
            samples[variant][code] = value
        result = assess(samples,target,self.spec)
        reference = samples['settling']
        ordered = all(reference[a]['mhz']<reference[b]['mhz'] for a,b in zip(codes,codes[1:]))
        target_passed = abs(reference[seed]['mhz']-target)<=target*self.spec['frequency_error_ppm']*1e-6
        result.update(target_mhz=target,coarse=coarse,seed=seed,samples=samples,
                      monotonic=ordered,target_passed=target_passed,calibration_model_qualified=False,release_qualified=False)
        result['passed'] = result['convergence_passed'] and ordered and target_passed
        label = f'local_n{count}_{point["corner"]}_{point["temperature_c"]}_{target}MHz'
        save(self.output/(label+'.json'),result)
        self.update(label,state='local_pass' if result['passed'] else 'local_nonpass')
        return result['passed']

    def execute(self):
        preferred = [('tt',27),('ss',125),('ff',-40),('fs',125)]
        points = preferred+[(c,t) for c in self.spec['corners'] for t in self.spec['temperatures_c'] if (c,t) not in preferred]
        for count in (160,144):
            results = [self.point(count,*points[0])]
            if results[0]['passed']:
                # TwoPVT points at a time; four one-case native workers total.
                # Submit only the next pair, so a failure stops expansion.
                with ThreadPoolExecutor(max_workers=2) as pvt_pool:
                    for i in range(1,len(points),2):
                        futures = [pvt_pool.submit(self.point,count,*pt) for pt in points[i:i+2]]
                        batch = [future.result() for future in futures]
                        results.extend(batch)
                        if any(not result['passed'] for result in batch):
                            break
            range_pass = covered(results,self.spec)
            save(self.output/f'candidate_{count}_range.json',dict(points=results,range_passed=range_pass,release_qualified=False))
            if not range_pass:
                continue
            local_pass = True
            for point in results:
                for mode in (400,300,250,100):
                    if not self.qualify_local(count,point,mode):
                        local_pass = False
                        break
                if not local_pass:
                    break
            if local_pass:
                state = 'LOCAL_CONVERGENCE_PASSED_MODEL_AND_PHYSICAL_GATES_OPEN'
                save(self.output/'decision.json',dict(state=state,candidate_for_model_validation=count,
                    calibration_model_qualified=False,selected=False,release_qualified=False,
                    next='Validate all model regions used in acquisition/tracking, dynamic interfaces, timing,60wholePLL cases and physical signoff. Never execute qualification with uncovered model lookups.'))
                self.update('decision',state=state,candidate_for_model_validation=count)
                return
        state = 'NO_CANDIDATE_PASSED_REQUIRED_RANGE_AND_LOCAL_GATES'
        save(self.output/'decision.json',dict(state=state,selected=False,release_qualified=False,
             global_unreachability_proven=False,next='Review retained measured blocker; no automatic design changes or identical retries.'))
        self.update('decision',state=state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    lockpath = ROOT/'build/timing400/native_queue.lock'
    lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        controller = Controller(args.output.resolve())
        try:
            controller.execute()
        except BaseException as error:
            controller.stopping.set()
            controller.update('decision',state='CONTROLLER_ERROR_NO_QUALIFICATION',error=repr(error))
            raise
        finally:
            controller.pool.shutdown(wait=True,cancel_futures=True)


if __name__=='__main__':
    main()
