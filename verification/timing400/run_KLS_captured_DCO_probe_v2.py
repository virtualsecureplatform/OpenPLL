#!/usr/bin/env python3
"""Bound a first full-matrix KLS test and independently audit its answers."""
import fcntl
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import time
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'fork_Xyce_KLS_001';owner=json.loads((campaign/'owner.json').read_text())
deadline=owner['deadline_uptime'];scratch=Path(owner['scratch'])
controls=campaign/'native_controls_002';control_owner=json.loads((controls/'owner.json').read_text())
out=campaign/'captured_DCO_probe_002';out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),control_runner_pid=control_owner['runner_pid'],
     deadline_uptime=deadline,budget_restarted=False,maximum_probe_wall_s=1800,
     address_space_limit_GiB=48,threads=4,automatic_identical_retry=False))
def status(state,**extra):
    save(out/'status.json',dict(state=state,deadline_uptime=deadline,
         release_qualified=False,adopted=False,**extra))
status('waiting_for_native_waveform_controls')
while not (controls/'assessment.json').exists():
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline-300:
        status('deadline_before_prerequisite_inconclusive');raise SystemExit(0)
    state=process(control_owner['runner_pid'])
    if not state['live'] or not any(s.endswith('check_fork_Xyce_KLS_controls_v2.py') for s in state['argv']):
        status('native_controls_terminal_without_pass');raise SystemExit(0)
    time.sleep(5)
control_proof=json.loads((controls/'assessment.json').read_text())
assert control_proof['fork_KLU_and_KLS_native_waveform_controls_passed']
source=Path(__file__).with_name('kls_captured_DCO_probe.cpp')
build=scratch/'build';linkfile=build/'src/CMakeFiles/Xyce.dir/link.txt'
inputs=base/'native_adapter_probe_inputs_001'
capture=base/'DCO_native_linear_system_capture_002/native_Jacobian.npz'
manifest=inputs/'assessment.json'
pins={**json.loads(manifest.read_text())['artifacts']}
for p in (Path(__file__).resolve(),source,linkfile,manifest,capture,controls/'assessment.json',
          campaign/'build_002/assessment.json'):
    pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
obj=scratch/'kls_captured_DCO_probe.o';binary=scratch/'kls_captured_DCO_probe'
compile_command=['/usr/bin/g++','-std=c++17','-O3','-I'+str(scratch/'KLS/include'),'-c',str(source),'-o',str(obj)]
link=shlex.split(linkfile.read_text())
assert link.count('CMakeFiles/Xyce.dir/Xyce.C.o')==1
link[link.index('CMakeFiles/Xyce.dir/Xyce.C.o')]=str(obj)
index=link.index('-o');assert link[index+1]=='Xyce';link[index+1]=str(binary)
for token in link:
    p=Path(token)
    if not p.is_absolute():p=build/'src'/p
    if p.is_file() and p!=obj:pins[str(p)]=digest(p)
child=None;receipts=[]
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(7200,7201))
try:
    for label,command in [('compile',compile_command),('link',link)]:
        started=time.monotonic()
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=build/'src',stdout=log,stderr=subprocess.STDOUT,
                start_new_session=True,preexec_fn=limits)
            status(label,child_pid=child.pid)
            code=child.wait(timeout=min(120,deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME)))
        receipts.append(dict(stage=label,exit_code=code,elapsed_s=time.monotonic()-started))
        save(out/'receipts.json',receipts);assert code==0,label
    for p in (obj,binary):pins[str(p)]=digest(p)
    with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
        admitted=False
        while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-2100:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:time.sleep(1);continue
            active=live_engines()
            mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
            if not active and mem['MemAvailable']>=40*1024**3:
                admitted=True;break
            fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_exclusive_large_probe',native_pids=active)
            time.sleep(5)
        if not admitted:raise TimeoutError('campaign cannot admit complete bounded probe')
        command=[str(binary),str(inputs),str(out)];started=time.monotonic()
        with (out/'probe.log').open('x') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                preexec_fn=limits,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE'))
            save(out/'launch.json',dict(pid=child.pid,command=command,wall_limit_s=1800,
                 address_space_limit_GiB=48,exclusive_large_probe=True,automatic_identical_retry=False))
            status('full_captured_matrix_KLS_probe_running',child_pid=child.pid)
            try:code=child.wait(timeout=1800)
            except subprocess.TimeoutExpired:raise TimeoutError('KLS full-matrix probe reached 1800-second limit')
        receipts.append(dict(stage='probe',exit_code=code,elapsed_s=time.monotonic()-started))
        save(out/'receipts.json',receipts);assert code==0,'KLS probe nonpass; retain phase log'
    matrix=load_npz(capture).tocsr()
    scale=1/np.asarray(abs(matrix).max(axis=1).toarray()).reshape(-1)
    checks=[]
    for label in ('native_Newton_RHS','known_solution'):
        rhs=np.fromfile(inputs/(label+'.bin'),dtype='<f8')
        solution_path=out/(label+'.solution.bin');solution=np.fromfile(solution_path,dtype='<f8')
        assert solution.shape==rhs.shape==(matrix.shape[0],) and np.isfinite(solution).all()
        residual=matrix@solution-rhs
        weighted=float(np.linalg.norm(scale*residual)/np.linalg.norm(scale*rhs))
        unweighted=float(np.linalg.norm(residual)/np.linalg.norm(rhs))
        check=dict(case=label,weighted_original_equation_residual=weighted,
                   unweighted_original_equation_residual=unweighted,weighted_limit=1e-12)
        checks.append(check);save(out/'independent_residual_observations.json',checks)
        assert weighted<=1e-12,check
        pins[str(solution_path)]=digest(solution_path)
    pins[str(out/'probe.log')]=digest(out/'probe.log')
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    shutil.copy2(binary,out/'kls_captured_DCO_probe')
    save(out/'assessment.json',dict(input_sha256=pins,checks=checks,receipts=receipts,
         full_captured_original_equation_KLS_checks_passed=True,
         KLS_default_certification_retained=True,external_weighted_residual_limit=1e-12,
         true_nonlinear_RHS_sequence_tested=False,refactor_accuracy_tested=False,
         full_DCO_transient_qualified=False,release_qualified=False,adopted=False))
    status('completed_full_matrix_KLS_checks')
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),
         source_matrix_modified=False,automatic_identical_retry=False,release_qualified=False))
    status('timeout_inconclusive' if isinstance(error,TimeoutError) else 'captured_matrix_probe_nonpass')
    raise
finally:stop()
