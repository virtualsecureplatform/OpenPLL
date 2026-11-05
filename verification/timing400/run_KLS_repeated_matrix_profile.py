#!/usr/bin/env python3
"""Bounded diagnosis of actual KLS defaults versus repeated-workload hints."""
import fcntl
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import time
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'KLS_runtime_diagnosis_001';owner=json.loads((campaign/'owner.json').read_text())
deadline=owner['deadline_uptime'];out=campaign/'repeated_matrix_001';out.mkdir(exist_ok=False)
scratch=Path('/tmp/openpll-xyce-kls-20261022-001');build=scratch/'build'
source=Path(__file__).with_name('kls_repeated_matrix_profile.cpp')
linkfile=build/'src/CMakeFiles/Xyce.dir/link.txt';inputs=base/'native_adapter_probe_inputs_001'
capture=base/'DCO_native_linear_system_capture_002/native_Jacobian.npz'
obj=scratch/'kls_repeated_matrix_profile.o';binary=scratch/'kls_repeated_matrix_profile'
pins={str(p):digest(p) for p in [Path(__file__).resolve(),source,linkfile,capture,inputs/'original_A.bin',campaign/'owner.json',scratch/'KLS/include/kls/kls.h']}
compile_command=['/usr/bin/g++','-std=c++17','-O3','-I'+str(scratch/'KLS/include'),'-c',str(source),'-o',str(obj)]
link=shlex.split(linkfile.read_text());assert link.count('CMakeFiles/Xyce.dir/Xyce.C.o')==1
link[link.index('CMakeFiles/Xyce.dir/Xyce.C.o')]=str(obj);link[link.index('-o')+1]=str(binary)
for token in link:
    p=Path(token)
    if not p.is_absolute():p=build/'src'/p
    if p.is_file() and p!=obj:pins[str(p)]=digest(p)
save(out/'owner.json',dict(runner_pid=os.getpid(),deadline_uptime=deadline,maximum_probe_wall_s=1200,
     address_space_limit_GiB=48,automatic_identical_retry=False,source_matrix_unchanged=True))
save(out/'input_manifest.json',dict(input_sha256=pins))
child=None
def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(4800,4801))
try:
    for label,command in [('compile',compile_command),('link',link)]:
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=build/'src',stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
            status(label,child_pid=child.pid);code=child.wait(timeout=min(120,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        assert code==0,label
    with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
        while True:
            assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-1200
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:time.sleep(1);continue
            active=live_engines();mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
            if not active and mem['MemAvailable']>=40*1024**3:break
            fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_exclusive_large_probe',native_pids=active);time.sleep(5)
        started=time.monotonic();command=[str(binary),str(inputs),str(out)]
        with (out/'probe.log').open('x') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                preexec_fn=limits,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE'))
            save(out/'launch.json',dict(pid=child.pid,command=command,maximum_wall_s=1200,automatic_identical_retry=False))
            status('profiling_repeated_KLS_calls',child_pid=child.pid)
            try:code=child.wait(timeout=1200)
            except subprocess.TimeoutExpired:raise TimeoutError('1200-second diagnosis probe limit')
        save(out/'native_receipt.json',dict(native_exit=code,elapsed_s=time.monotonic()-started));assert code==0,'KLS profile nonpass; see phase log'
    matrix=load_npz(capture).tocsr();original=matrix.copy();n=matrix.shape[0]
    x=.1*(np.sin(.013*np.arange(n))+np.cos(.027*np.arange(n)))
    rr=np.repeat(np.arange(n),np.diff(matrix.indptr));diagonal=(rr==matrix.indices)&(rr%17==0)
    checks=[]
    for variant in ('native_defaults','hinted'):
        for case in ('original','sparse_diagonal','global_scale','restore'):
            matrix=original.copy()
            if case=='sparse_diagonal':matrix.data[diagonal]+=1e-6*abs(matrix.data[diagonal])
            if case=='global_scale':matrix.data*=1.01
            stem=out/(variant+'_'+case)
            rhs_path=Path(str(stem)+'.rhs.bin');answer_path=Path(str(stem)+'.solution.bin')
            rhs=np.fromfile(rhs_path,dtype='<f8');answer=np.fromfile(answer_path,dtype='<f8')
            assert rhs.shape==answer.shape==(n,) and np.isfinite(answer).all()
            expected=matrix@x;absolute=abs(matrix)@abs(x);terms=np.diff(matrix.indptr);eps=np.finfo(float).eps
            bound=8*(terms+1)*eps/(1-(terms+1)*eps)*absolute
            assert np.all(abs(rhs-expected)<=bound)
            scale=1/np.asarray(abs(matrix).max(axis=1).toarray()).reshape(-1)
            residual=float(np.linalg.norm(scale*(matrix@answer-rhs))/np.linalg.norm(scale*rhs))
            error=float(max(abs(answer-x)))
            checks.append(dict(variant=variant,case=case,weighted_original_equation_residual=residual,known_solution_error_inf=error))
            save(out/'independent_observations.json',checks)
            assert residual<=1e-12 and error<1e-7,checks[-1]
            for p in (rhs_path,answer_path):pins[str(p)]=digest(p)
    records=[json.loads(line) for line in (out/'probe.log').read_text().splitlines() if line.startswith('{')]
    assert len(records)==16 and all(r['status']==0 for r in records)
    for p in (obj,binary,out/'probe.log'):pins[str(p)]=digest(p)
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    save(out/'assessment.json',dict(input_sha256=pins,phase_records=records,checks=checks,
         original_equation_checks_passed=True,synthetic_matrix_changes=True,
         actual_transient_Newton_matrix_sequence_profiled=False,
         native_default_lifecycle_hints=0,comparison_lifecycle_hints=20000,
         certification_unchanged=True,release_qualified=False))
    status('completed_repeated_matrix_profile')
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False));status('profile_nonpass');raise
finally:stop()
