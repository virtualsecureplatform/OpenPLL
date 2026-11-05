#!/usr/bin/env python3
"""Stop a timing-only native diagnostic after 12 calls or 20 minutes."""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'KLS_runtime_diagnosis_001';owner=json.loads((campaign/'owner.json').read_text());deadline=owner['deadline_uptime']
out=campaign/'native_prefix_001';out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),deadline_uptime=deadline,maximum_native_wall_s=1200,
     stop_after_completed_solver_calls=12,native_qualification_retried=False,
     purpose='Timing-only prefix diagnostic; stop before full transient qualification'))
def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
build=campaign/'instrumented_build_001/assessment.json'
assert build.exists() and json.loads(build.read_text())['adapter_regression_passed']
built=json.loads(build.read_text());binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
prior=base/'fork_Xyce_KLS_001/DCO_nom_tt27_c0_f247_80ns_001'
source=prior/'point.cir';source_proof=json.loads((prior/'assessment.json').read_text())
assert digest(source)==source_proof['input_sha256'][str(source)]
deck=out/'point.cir';deck.write_bytes(source.read_bytes())
pins={str(p):digest(p) for p in [Path(__file__).resolve(),build,binary,source,deck,campaign/'owner.json']}
pins.update(source_proof['input_sha256'])
for p,sha in pins.items():assert digest(Path(p))==sha,p
# The full-matrix profiler is not named Xyce; explicitly honor its live handle.
probe=campaign/'repeated_matrix_001/launch.json'
status('waiting_for_existing_large_matrix_probe')
while probe.exists():
    launch=json.loads(probe.read_text());identity=process(launch['pid'])
    if not identity['live']:break
    assert identity['argv']==launch['command']
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline-1200:
        status('deadline_before_prefix_admission');raise SystemExit(0)
    time.sleep(5)
child=None
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(4800,4801))
try:
    with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
        while True:
            assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-1200
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:time.sleep(1);continue
            active=live_engines();mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
            if not active and mem['MemAvailable']>=40*1024**3:break
            fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_exclusive_large_prefix',native_pids=active);time.sleep(5)
        log_path=out/'native.log';command=[str(binary),'-quiet','-o',str(out/'point'),str(deck)]
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_KLS_CALL_PROFILE='1')
        env.pop('OPENPLL_WIRE_PC',None);env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
        with log_path.open('x') as log:
            child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,
                env=env,start_new_session=True,preexec_fn=limits)
        started=time.monotonic();finish=min(started+1200,started+deadline-120-time.clock_gettime(time.CLOCK_BOOTTIME))
        save(out/'launch.json',dict(pid=child.pid,command=command,maximum_wall_s=1200,
             target_completed_calls=12,original_deck_preserved=True,instrumentation_only=True))
    records=[];stop_reason=None
    while child.poll() is None:
        text=log_path.read_text();lines=text.splitlines()
        if text and not text.endswith('\n'):lines.pop()
        records=[dict(token.split('=',1) for token in s.split()[1:]) for s in lines if s.startswith('OpenPLL_KLS_call ')]
        status('timing_native_prefix',native_pid=child.pid,completed_solver_calls=len(records),elapsed_s=time.monotonic()-started)
        if len(records)>=12:stop_reason='planned_completed_call_count';stop();break
        if time.monotonic()>=finish:stop_reason='bounded_diagnostic_deadline';stop();break
        time.sleep(2)
    stop()
    raw=log_path.read_text();records=[dict(token.split('=',1) for token in s.split()[1:]) for s in raw.splitlines() if s.startswith('OpenPLL_KLS_call ')]
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    pins[str(log_path)]=digest(log_path)
    for i,r in enumerate(records):
        assert int(r['rows'])==174551 and float(r['total'])>=0,r
    phases=['analysis','values','factor','refactor_solve','solve','imports','exports']
    sums={phase:sum(float(r[phase]) for r in records) for phase in phases}
    total=sum(float(r['total']) for r in records)
    save(out/'assessment.json',dict(input_sha256=pins,call_records=records,completed_solver_calls=len(records),
         measured_total_adapter_s=total,exclusive_phase_sums=sums,
         exclusive_phase_fractions={p:v/total for p,v in sums.items()} if total else {},
         native_exit=child.returncode,stop_reason=stop_reason,native_wall_s=time.monotonic()-started,
         original_transient_settings_retained=True,instrumentation_changes_numerical_algorithm=False,
         completed_calls_not_independent_accuracy_certificates=True,full_transient_qualification_attempted=False,
         release_qualified=False))
    status('completed_bounded_native_prefix_profile',completed_solver_calls=len(records),stop_reason=stop_reason)
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False));raise
finally:stop()
