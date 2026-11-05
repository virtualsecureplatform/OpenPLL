#!/usr/bin/env python3
"""Check user fork/KLS on retained signed-C BSIM controls before DCO use."""
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
import numpy as np
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines
from check_stock_threaded_solver_controls_v2 import read_wave,crossing

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'fork_Xyce_KLS_001';owner=json.loads((campaign/'owner.json').read_text())
deadline=owner['deadline_uptime'];build=campaign/'build_002'
build_owner=json.loads((build/'owner.json').read_text());builder=build_owner['runner_pid']
out=campaign/'native_controls_002';out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),builder_pid=builder,
     deadline_uptime=deadline,budget_restarted=False,automatic_identical_retry=False))
def status(state,**extra):
    save(out/'status.json',dict(state=state,deadline_uptime=deadline,
         release_qualified=False,adopted=False,**extra))
status('waiting_for_identified_fork_build')
while not (build/'assessment.json').exists():
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
        status('deadline_before_build_inconclusive');raise SystemExit(0)
    current=process(builder)
    if not current['live'] or not any(s.endswith('build_fork_Xyce_KLS_adapter_fix.py') for s in current['argv']):
        status('build_terminal_without_pass',builder=current);raise SystemExit(0)
    time.sleep(5)
proof=json.loads((build/'assessment.json').read_text())
assert proof['fork_Xyce_KLS_build_passed'] and proof['adapter_regression_passed']
binary=Path(proof['binary']);assert digest(binary)==proof['binary_sha256']
prior=base/'bounded_reuse_native_controls_002'
reference=json.loads((prior/'assessment.json').read_text())
assert json.loads((base/'bounded_reuse_native_controls_audit_002/assessment.json').read_text())['completed_native_control_audit_passed']
pins={str(p):digest(p) for p in (Path(__file__).resolve(),build/'assessment.json',binary,prior/'assessment.json')}
receipts=[];comparisons=[]
for variant in ['default_trapezoid','gear_baseline','gear_timestep_holdout','gear_tolerance_holdout']:
    original=prior/(variant+'_stock.cir');wave=Path(str(original)+'.prn')
    assert digest(original)==reference['input_sha256'][str(original)]
    assert digest(wave)==reference['artifacts'][str(wave)]
    pins[str(original)]=digest(original);pins[str(wave)]=digest(wave)
    reference_wave=read_wave(wave)
    choices=[('fork_KLU',1),('fork_KLS',1)]+([('fork_KLS',4)] if variant=='gear_baseline' else [])
    for solver,threads in choices:
        label=variant+'_'+solver+'_'+str(threads)+'t';folder=out/label;folder.mkdir()
        text=original.read_text();old='.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0'
        assert text.count(old)==1
        replacement=old if solver=='fork_KLU' else f'.options LINSOL TYPE=KLS KLS_THREADS={threads} KLS_PROFILE=1 TR_PARTITION=0 TR_AMD=0'
        deck=folder/'control.cir';deck.write_text(text.replace(old,replacement))
        pins[str(deck)]=digest(deck)
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE')
        env.pop('OPENPLL_WIRE_PC',None);env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
        child=None
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-300:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:time.sleep(1);continue
                active=live_engines()
                mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
                if len(active)<4 and mem['MemAvailable']>=8*1024**3:
                    def limits():
                        resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
                        resource.setrlimit(resource.RLIMIT_CPU,(120,121))
                    command=[str(binary),'-quiet','-o',str(folder/'control'),str(deck)]
                    started=time.monotonic()
                    with (folder/'native.log').open('x') as log:
                        child=subprocess.Popen(command,cwd=folder,env=env,stdout=log,
                            stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
                    save(folder/'launch.json',dict(native_pid=child.pid,command=command,
                         observed_native_before=active,maximum_native_workers=4,automatic_identical_retry=False))
                    break
                fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_native_capacity',case=label)
                time.sleep(2)
        if child is None:status('deadline_before_admission_inconclusive',case=label);raise SystemExit(0)
        status('native_running',case=label,native_pid=child.pid)
        try:code=child.wait(timeout=min(120,max(.001,deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            code=child.returncode
        receipts.append(dict(case=label,native_exit=code,elapsed_s=time.monotonic()-started))
        save(out/'native_receipts.json',receipts)
        assert code==0,receipts[-1]
        native=read_wave(folder/'control.prn')
        grid=np.linspace(0,8e-9,8001)
        differences=[float(max(abs(np.interp(grid,reference_wave[:,0],reference_wave[:,i])-
                     np.interp(grid,native[:,0],native[:,i])))) for i in range(1,5)]
        a,b=crossing(reference_wave),crossing(native);assert len(a)==len(b)
        edge=max(abs(x-y) for x,y in zip(a,b))
        current_scale=max(float(max(abs(reference_wave[:,4]))),float(max(abs(native[:,4]))),1e-12)
        assert max(differences[:2])<1e-5 and differences[2]<2e-3
        assert differences[3]<1e-3*current_scale+1e-10 and edge<1e-13
        if solver=='fork_KLS':assert 'KLS profile calls = ' in (folder/'native.log').read_text()
        comparisons.append(dict(case=label,signal_maximum_absolute_differences=differences,
             maximum_rising_crossing_difference_s=edge,KLS_selected=solver=='fork_KLS'))
        for p in (folder/'native.log',folder/'control.prn',folder/'launch.json'):pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'assessment.json',dict(input_sha256=pins,receipts=receipts,comparisons=comparisons,
     fork_KLU_and_KLS_native_waveform_controls_passed=True,
     KLS_one_and_four_thread_controls_passed=True,signed_capacitance_retained=True,
     timestep_and_tolerance_holdouts_passed=True,transient_tolerances_unchanged=True,
     every_linear_answer_independently_audited=False,full_DCO_equations_tested=False,
     release_qualified=False,adopted=False))
status('completed_native_waveform_controls')
