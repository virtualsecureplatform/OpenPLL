#!/usr/bin/env python3
"""Gracefully finish a 20 ps physical diagnostic to flush KLS phase reports."""
import fcntl,json,os,re,resource,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';campaign=base/'KLS_detailed_profile_001';deadline=json.loads((campaign/'owner.json').read_text())['deadline_uptime']
controls=campaign/'native_controls_001/assessment.json';assert json.loads(controls.read_text())['native_waveform_controls_passed']
buildproof=campaign/'native_build_002/assessment.json';built=json.loads(buildproof.read_text());binary=Path(built['profile_binary']);assert digest(binary)==built['profile_binary_sha256']
original=base/'KLS_preconditioner_001/DCO_nom_tt27_c0_f247_80ns_001/point.cir';metadata=base/'native_wire_preconditioner_metadata_001/wire_C.bin';reference=base/'DCO_bounded_reuse_variable_map_001/candidate.names'
out=campaign/'native_short_profile_001';out.mkdir(exist_ok=False)
text=original.read_text();old='.tran 20p 80n 0 10p UIC';new='.tran 20p 20p 0 10p UIC';assert text.count(old)==1
point=out/'point.cir';point.write_text(text.replace(old,new))
pins=json.loads((original.parent/'input_manifest.json').read_text())['input_sha256']
for p in [Path(__file__).resolve(),campaign/'owner.json',controls,buildproof,binary,original,point,metadata,reference]:pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'input_manifest.json',dict(input_sha256=pins,diagnostic_end_time_ps=20,original_80ns_qualification_attempted=False,full_physical_capacitances_retained=True,original_Gear_tolerances_retained=True))
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not live_engines()
mem={t.split(':')[0]:int(t.split()[1])*1024 for t in Path('/proc/meminfo').read_text().splitlines()};assert mem['MemAvailable']>=40*1024**3
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(metadata),OPENPLL_KLS_COMPARE_THREADS='4',OPENPLL_KLS_COMPARE_POLICY='application_managed');env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
child=None;receipts=[]
def limit():resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
def stop():
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def names(p):return {int(t.split()[0]):t.split()[1].upper() for t in p.read_text().splitlines()[1:]}
try:
 for stage in ['variable_map','transient']:
  command=[str(binary),'-quiet']+(['-namesfile',str(out/'candidate.names')] if stage=='variable_map' else ['-o',str(out/'point')])+[str(point)]
  start=time.monotonic()
  with (out/(stage+'.log')).open('x') as log:child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit)
  save(out/(stage+'_launch.json'),dict(pid=child.pid,command=command,automatic_identical_retry=False))
  save(out/'status.json',dict(state=stage+'_running',native_pid=child.pid,deadline_uptime=deadline,release_qualified=False))
  child.wait(timeout=min(900,max(.001,deadline-60-time.clock_gettime(time.CLOCK_BOOTTIME))))
  receipts.append(dict(stage=stage,exit_code=child.returncode,wall_s=time.monotonic()-start));save(out/'receipts.json',receipts);assert child.returncode==0,stage
  if stage=='variable_map':assert names(out/'candidate.names')==names(reference)
 log=(out/'transient.log').read_text();calls=[dict(call=int(a),iterations=int(b),residual=float(c),seconds=float(d),status=int(e)) for a,b,c,d,e in re.findall(r'OpenPLL_wire_PC call=(\d+).*?iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)',log)]
 assert calls and all(v['status']==0 and v['residual']<=1e-12 for v in calls)
 phase=next(line for line in log.splitlines() if line.startswith('solve_profile '));kernels=next(line for line in log.splitlines() if line.startswith('klu_phase_profile '))
 coarse=[]
 for line in log.splitlines():
  if line.startswith('kls_coarse slot='):
   pairs=dict(re.findall(r'(\w+)=([^ ]+)',line));coarse.append({k:(v if k in ('name','role') else int(v)) for k,v in pairs.items()})
 assert len(coarse)==50 and 'kls_coarse_summary errors=0' in log
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'assessment.json',dict(input_sha256=pins,completed_short_native_transient=True,duration_ps=20,linear_solves=len(calls),all_logged_full_equation_residual_checks_passed=True,adapter_seconds=sum(v['seconds'] for v in calls),calls=calls,api_phase_profile={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',phase)},vendor_kernel_profile={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',kernels)},coarse_scopes=coarse,instrumented_diagnostic_not_production_speed_measurement=True,startup_segment_not_steady_state_qualification=True,release_qualified=False))
 save(out/'status.json',dict(state='completed_short_native_profile',release_qualified=False))
except Exception as e:
 stop();save(out/'failure_receipt.json',dict(error_type=type(e).__name__,message=str(e),diagnostic_scope_only=True));raise
finally:stop()
