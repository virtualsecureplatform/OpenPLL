#!/usr/bin/env python3
"""Run one prepared, final-loading DCO case with the approved 48h KLU policy.

Preparation must supply extraction, native variable-map, solver-control and
captured-equation receipts for the exact candidate. Old diagnostic decks cannot
be promoted by changing a path or a qualification flag.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
from common import ROOT, PROFILE, source_pins, spec, save, sha, verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from run_DCO_domain_point_v3 import live_engines, model_files
from run_DCO_stock_threaded_point_v2 import rows


def spice_number(token):
    match=re.fullmatch(r'([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)([a-z]*)',token.lower())
    scale={'':1.,'s':1.,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15}
    if not match or match[2] not in scale:raise ValueError('unsupported SPICE number: '+token)
    return float(match[1])*scale[match[2]]


def validate_settings(params, deck):
    variants={'baseline':(80,20,10,1e-5,1e-9), 'step':(80,20,5,1e-5,1e-9),
              'tolerance':(80,20,10,1e-6,1e-10), 'settling':(160,40,10,1e-5,1e-9)}
    expected=variants.get(params['variant'])
    actual=tuple(params[k] for k in ('duration_ns','measurement_start_ns','max_step_ps','reltol','abstol'))
    if expected is None or actual!=expected:raise ValueError('unsupported numerical variant')
    transient=re.findall(r'^\s*\.tran\s+([^\n]+)',deck,re.M|re.I)
    if len(transient)!=1:raise ValueError('one transient directive required')
    fields=transient[0].split()
    if len(fields)<4 or not math.isclose(spice_number(fields[1]),expected[0]*1e-9,rel_tol=1e-12):
        raise ValueError('transient duration does not match manifest')
    if spice_number(fields[2])!=0 or not math.isclose(spice_number(fields[3]),expected[2]*1e-12,rel_tol=1e-12):
        raise ValueError('transient maximum step does not match manifest')
    options=' '.join(re.findall(r'^\s*\.options\s+TIMEINT\s+([^\n]+)',deck,re.M|re.I))
    values={k.lower():v.lower() for k,v in re.findall(r'(\w+)\s*=\s*(\S+)',options)}
    if (values.get('method')!='gear' or float(values.get('reltol','nan'))!=expected[3]
            or float(values.get('abstol','nan'))!=expected[4]):
        raise ValueError('integration settings do not match manifest')
    if not re.search(r'^\s*\.lib\s+\S+\s+'+params['corner']+r'\s*$',deck,re.M|re.I):
        raise ValueError('process model does not match manifest')
    if not re.search(r'^\s*\.options\s+DEVICE\s+TEMP\s*=\s*27\s*$',deck,re.M|re.I):
        raise ValueError('temperature does not match manifest')


def prepared(path):
    value=json.loads(path.read_text());profile=spec()
    if value['profile_sha256']!=sha(PROFILE) or value['candidate_source_sha256']!=source_pins():
        raise ValueError('prepared candidate/profile identity mismatch')
    if value['scope']!='final_loaded_dco':
        raise ValueError('final parent loading required')
    verify(value['input_sha256']);verify(value['candidate_physical_sha256'])
    if not value['candidate_physical_sha256']:
        raise ValueError('final physical identity required')
    params=value['parameters']
    if (params['corner'] not in profile['corners'] or params['temperature_c']!=27
            or params['supply_v']!=1.8 or not 0<=params['coarse']<=47
            or not 8<=params['fine']<=247):
        raise ValueError('unsupported prototype point')
    for key in ('deck','binary','metadata','reference_names'):
        if value[key] not in value['input_sha256']:
            raise ValueError('unpinned native input: '+key)
    validate_settings(params,Path(value['deck']).read_text())
    flags={'extraction_receipt':'physical_domain_complete',
           'mapping_receipt':'native_GID_order_verified',
           'solver_controls_receipt':'native_waveform_controls_passed',
           'equation_receipt':'all_original_equation_residual_checks_passed'}
    for key,flag in flags.items():
        receipt=value[key]
        if receipt not in value['input_sha256']:
            raise ValueError('unpinned native receipt: '+key)
        report=json.loads(Path(receipt).read_text())
        if not report[flag]:raise ValueError('native prerequisite nonpass: '+key)
        verify(report['input_sha256']);verify(report['artifacts'])
        if key=='extraction_receipt':
            if (report['candidate_physical_sha256']!=value['candidate_physical_sha256']
                    or report['candidate_source_sha256']!=value['candidate_source_sha256']):
                raise ValueError('extraction candidate mismatch')
        else:
            if report['input_sha256'].get(value['binary'])!=sha(value['binary']):
                raise ValueError('receipt does not cover selected binary')
        if key=='mapping_receipt':
            for target in ('deck','metadata','reference_names'):
                if report['input_sha256'].get(value[target],report['artifacts'].get(value[target]))!=sha(value[target]):
                    raise ValueError('native mapping identity mismatch: '+target)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared-case',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    policy=spec()['native'];now=datetime.now(timezone.utc)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+policy['wall_limit_s']
    native_deadline=deadline-policy['assessment_reserve_s']
    owner=dict(runner_pid=os.getpid(),started_utc=now.isoformat(),deadline_uptime=deadline,
        deadline_utc=(now+timedelta(seconds=policy['wall_limit_s'])).isoformat(),
        wall_limit_s=policy['wall_limit_s'],automatic_identical_retry=False)
    save(out/'owner.json',owner);child=None
    def status(state,**extra):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            runner_pid=os.getpid(),deadline_utc=owner['deadline_utc'],prototype_handoff_qualified=False,**extra))
    def stop():
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    def limits():
        cap=policy['address_space_limit_GiB']*1024**3
        resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
        cpu=max(1,int(native_deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+1))
    def interrupted(number, frame):
        raise SystemExit('interrupted by signal '+str(number))
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    try:
        status('checking_native_prerequisites')
        value=prepared(a.prepared_case.resolve())
        pins=dict(value['input_sha256']);pins.update(value['candidate_physical_sha256'])
        for path in [a.prepared_case.resolve(),Path(__file__).resolve(),Path(__file__).with_name('common.py'),PROFILE]:
            pins[str(path)]=sha(path)
        deck=out/'point.cir';deck.write_bytes(Path(value['deck']).read_bytes())
        for path in model_files(deck,native_deadline):
            if path!=deck and pins.get(str(path))!=sha(path):
                raise ValueError('unpinned physical model dependency: '+str(path))
        pins[str(deck)]=sha(deck)
        save(out/'input_manifest.json',dict(input_sha256=pins,parameters=value['parameters']))
        command=[value['binary'],'-quiet','-o',str(deck),str(deck)]
        env=dict(os.environ,OPENPLL_WIRE_PC=value['metadata'],OMP_NUM_THREADS='1',
                 OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
        with (ROOT/'build/timing400/guarded_native_admission.lock').open('a+') as lock:
            while time.clock_gettime(time.CLOCK_BOOTTIME)<native_deadline:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:time.sleep(1);continue
                active=live_engines()
                mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
                if not active and mem['MemAvailable']>=policy['minimum_available_memory_GiB']*1024**3:
                    with (out/'native.log').open('x') as log:
                        child=subprocess.Popen(command,cwd=out,env=env,stdout=log,
                            stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
                    save(out/'launch.json',dict(pid=child.pid,command=command,observed_native_before=active))
                    break
                fcntl.flock(lock,fcntl.LOCK_UN)
                status('queued_for_exclusive_native_capacity',observed_native_pids=active)
                time.sleep(5)
        if child is None:raise TimeoutError('budget exhausted before admission')
        expression=re.compile(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(-?\d+)')
        count=bad=0;maximum=0.;wave=Path(str(deck)+'.prn')
        last_time=-1.;last_progress=time.monotonic();reason=None
        with (out/'native.log').open() as log:
            while True:
                for line in log:
                    match=expression.fullmatch(line.strip())
                    if match:
                        residual=float(match[4]);count+=1
                        bad+=int(not math.isfinite(residual) or residual>policy['scaled_true_residual_limit'] or int(match[6])!=0)
                        maximum=max(maximum,residual)
                data=rows(wave);current=data[-1][0] if data else 0.
                if current>last_time:last_time=current;last_progress=time.monotonic()
                status('native_transient_running',native_pid=child.pid,simulation_time_s=current,
                       samples=len(data),completed_linear_solves=count,invalid_linear_solves=bad,
                       maximum_scaled_true_residual=maximum)
                if child.poll() is not None:break
                if bad:reason='numerical_gate_nonpass'
                elif time.clock_gettime(time.CLOCK_BOOTTIME)>=native_deadline:reason='campaign_budget'
                elif time.monotonic()-last_progress>3600:reason='no_transient_progress_for_one_hour'
                if reason:stop();continue
                time.sleep(10)
        duration=value['parameters']['duration_ns']*1e-9
        complete=bool(child.returncode==0 and data and current>=duration*(1-1e-9)
                      and 'End of Xyce(TM) Simulation' in wave.read_text())
        # Independently rescan the final log so a partial live write cannot
        # hide a failed solve or silently reduce the coverage count.
        count=bad=0;maximum=0.
        with (out/'native.log').open() as log:
            for line in log:
                if not line.startswith('OpenPLL_wire_PC '):continue
                match=expression.fullmatch(line.strip())
                if not match:raise ValueError('malformed terminal solver evidence')
                residual=float(match[4]);count+=1
                bad+=int(not math.isfinite(residual) or residual>policy['scaled_true_residual_limit'] or int(match[6])!=0)
                maximum=max(maximum,residual)
        if complete:
            counts=re.findall(r'Number Linear Solves:\s*(\d+)',(out/'native.log').read_text())
            if not counts or int(counts[-1])!=count:
                raise ValueError('solver evidence count does not cover all native linear solves')
        assert all(math.isfinite(v) for row in data for v in row)
        assert all(x[0]<y[0] for x,y in zip(data,data[1:]))
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(path):sha(path) for path in (wave,out/'native.log') if path.exists()},
            completed_full_native_transient=complete,native_exit=child.returncode,stop_reason=reason,
            simulation_time_s=current,samples=len(data),adapter_linear_solves=count,
            invalid_linear_solves=bad,maximum_scaled_true_residual=maximum,
            full_residual_gate_passed=bool(count and not bad),dco_model_qualified=False,
            prototype_handoff_qualified=False))
        status('completed_native_point' if complete and count and not bad else 'native_inconclusive_or_nonpass',
               simulation_time_s=current,stop_reason=reason)
    except BaseException as error:
        stop();status('native_runner_nonpass',reason=str(error));raise
    finally:stop()


if __name__=='__main__':main()
