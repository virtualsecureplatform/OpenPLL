#!/usr/bin/env python3
"""Run user-selected KLS only after native controls and captured equations pass."""
from datetime import datetime,timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines,model_files
from run_DCO_stock_threaded_point_v2 import rows

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'KLS_preconditioner_001';owner=json.loads((campaign/'owner.json').read_text())
deadline=owner['deadline_uptime']
probe=base/'native_KLS_rhs_probe_checks_001'
changes=base/'native_KLS_reuse_probe_checks_001/assessment.json'
assert json.loads((probe/'assessment.json').read_text())['all_original_equation_residual_checks_passed']
assert json.loads(changes.read_text())['all_original_equation_residual_checks_passed']
controls=campaign/'native_controls_001/assessment.json'
assert json.loads(controls.read_text())['native_waveform_controls_passed']
build=campaign/'build_001/assessment.json';built=json.loads(build.read_text())
binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
out=campaign/'DCO_nom_tt27_c0_f247_80ns_001';out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),deadline_uptime=deadline,
     started_utc=datetime.now(timezone.utc).isoformat(),budget_restarted=False,
     KLS_threads=4,total_campaign_wall_limit_s=43200,automatic_identical_retry=False))
def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,
         release_qualified=False,adopted=False,**extra))
prior=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
source=prior/'point.cir';original=source.read_text()
old='.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0 KLU_REPIVOT=0'
new='.options LINSOL TYPE=KLS KLS_THREADS=4 KLS_PROFILE=1 TR_PARTITION=0 TR_AMD=0'
assert original.count(old)==1
deck=out/'point.cir';deck.write_text(original.replace(old,new))
assert deck.read_text().replace(new,old)==original
assert '.options TIMEINT RELTOL=1e-05 ABSTOL=1e-09 METHOD=GEAR' in original
assert '.tran 20p 80n 0 10p UIC' in original
pins={str(p):digest(p) for p in (Path(__file__).resolve(),probe/'assessment.json',controls,
     build,binary,source,deck,campaign/'owner.json',Path(__file__).with_name('run_DCO_stock_threaded_point_v2.py'))}
for p in model_files(deck,deadline-300):pins[str(p)]=digest(p)
reference_names=base/'DCO_bounded_reuse_variable_map_001/candidate.names'
pins[str(reference_names)]=digest(reference_names)
save(out/'input_manifest.json',dict(input_sha256=pins,physical_deck_unchanged_except_solver=True,
     duration_ns=80,measurement_start_ns=20,maximum_step_ps=10,method='GEAR',
     relative_tolerance=1e-5,absolute_tolerance=1e-9,nominal_supply_v=1.8,
     KLS_default_certification_retained=True,source_patch=built['source_patch']))
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE')
env['OPENPLL_WIRE_PC']=str(base/'native_wire_preconditioner_metadata_001/wire_C.bin')
env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
assert digest(Path(env['OPENPLL_WIRE_PC']))=='f78520d1da4cea105a624e95810dc5d3487688cbbb0c959819fac36b6c1da9f0'
pins[env['OPENPLL_WIRE_PC']]=digest(Path(env['OPENPLL_WIRE_PC']));env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
child=None;receipts=[]
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
    seconds=max(1,int(4*(deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME))))
    resource.setrlimit(resource.RLIMIT_CPU,(seconds,seconds+1))
try:
    for stage in ('variable_map','transient'):
        assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-300
        names=out/'candidate.names'
        command=[str(binary),'-quiet']
        if stage=='variable_map':command+=['-namesfile',str(names)]
        else:command+=['-o',str(out/'point')]
        command+=[str(deck)];started=time.monotonic();admitted=False
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-300:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:time.sleep(1);continue
                active=live_engines()
                mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
                # No other large simulation or solver probe may overlap.
                if not active and mem['MemAvailable']>=40*1024**3:
                    with (out/(stage+'.log')).open('x') as log:
                        child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,
                            env=env,start_new_session=True,preexec_fn=limits)
                    save(out/(stage+'_launch.json'),dict(pid=child.pid,command=command,
                         observed_native_before=active,maximum_native_workers=4,
                         exclusive_large_case=True,address_space_limit_GiB=48,automatic_identical_retry=False))
                    admitted=True;break
                fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_exclusive_large_case',stage=stage,native_pids=active)
                time.sleep(5)
        if not admitted:raise TimeoutError('campaign deadline before admission')
        status('native_'+stage+'_running',native_pid=child.pid)
        timed_out=False
        try:code=child.wait(timeout=min(900 if stage=='variable_map' else 43200,
             max(.001,deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:timed_out=True;stop();code=child.returncode
        receipts.append(dict(stage=stage,native_exit=code,timed_out=timed_out,elapsed_s=time.monotonic()-started))
        save(out/'native_receipts.json',receipts)
        if stage=='variable_map':
            assert code==0 and not timed_out,'native variable-map stage nonpass'
            def read_names(path):
                lines=path.read_text().splitlines();assert lines[0]=='HEADER'
                result={int(s.split()[0]):s.split()[1].upper() for s in lines[1:]}
                assert set(result)==set(range(len(result))) and len(set(result.values()))==len(result)
                return result
            previous,current=read_names(reference_names),read_names(names)
            save(out/'variable_map_comparison.json',dict(reference_count=len(previous),candidate_count=len(current),
                 same_variable_names=set(previous.values())==set(current.values()),
                 identical_GID_order=previous==current))
            assert previous==current,'preconditioner requires identical variable GID order'
            pins[str(names)]=digest(names)
            continue
        data=rows(out/'point.prn')
        assert all(all(math.isfinite(v) for v in row) for row in data)
        assert all(a[0]<b[0] for a,b in zip(data,data[1:]))
        complete=code==0 and data and data[-1][0]>=80e-9*(1-1e-9)
        edges=[]
        for left,right in zip(data,data[1:]):
            if left[1]<.9<=right[1]:
                t=left[0]+(.9-left[1])*(right[0]-left[0])/(right[1]-left[1])
                if t>=20e-9:edges.append(t)
        metrics=dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6,periods=len(edges)-1) if len(edges)>=4 else None
        for p,sha in pins.items():assert digest(Path(p))==sha,p
        save(out/'assessment.json',dict(input_sha256=pins,native_receipts=receipts,
             completed_full_native_transient=bool(complete),native_exit=code,
             budget_stop_inconclusive=timed_out,samples=len(data),simulation_time_s=data[-1][0] if data else None,
             metrics=metrics,method_frequency_convergence_qualified=False,
             every_nonlinear_linear_answer_independently_audited=False,
             release_qualified=False,adopted=False))
        status('completed_native_diagnostic' if complete and metrics else 'native_inconclusive_or_nonpass',metrics=metrics)
except Exception as error:
    stop();save(out/'runner_failure.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False))
    status('runner_nonpass');raise
finally:stop()
