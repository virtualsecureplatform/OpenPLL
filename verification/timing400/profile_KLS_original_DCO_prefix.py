#!/usr/bin/env python3
"""Profile the original transient grid; exit after 64 accepted Newton solves."""
import fcntl,json,os,re,resource,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';c=base/'KLS_detailed_profile_001';deadline=json.loads((c/'owner.json').read_text())['deadline_uptime'];proof=json.loads((c/'native_boundary_build_001/assessment.json').read_text());binary=Path(proof['binary']);assert digest(binary)==proof['binary_sha256']
assert json.loads((c/'native_controls_001/assessment.json').read_text())['native_waveform_controls_passed']
original=base/'KLS_preconditioner_001/DCO_nom_tt27_c0_f247_80ns_001/point.cir';old=c/'native_short_profile_001';out=c/'native_prefix_profile_001';out.mkdir(exist_ok=False);point=out/'point.cir';point.write_bytes(original.read_bytes())
assert old.joinpath('point.cir').read_text().replace('.tran 20p 20p 0 10p UIC','.tran 20p 80n 0 10p UIC')==point.read_text()
def names(p):return {int(t.split()[0]):t.split()[1].upper() for t in p.read_text().splitlines()[1:]}
reference=base/'DCO_bounded_reuse_variable_map_001/candidate.names';assert names(old/'candidate.names')==names(reference)
assert json.loads((old/'receipts.json').read_text())[0]['exit_code']==0
metadata=base/'native_wire_preconditioner_metadata_001/wire_C.bin';pins=json.loads((original.parent/'input_manifest.json').read_text())['input_sha256']
for p in [Path(__file__).resolve(),c/'owner.json',c/'native_boundary_build_001/assessment.json',binary,point,metadata,old/'point.cir',old/'candidate.names',reference]:pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'input_manifest.json',dict(input_sha256=pins,original_deck_byte_identical=True,planned_accepted_solves=64,variable_map_reused_from_same_circuit_with_only_tran_end_time_different=True,topology_objects_unchanged=True,full_80ns_qualification_attempted=False))
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not live_engines()
mem={t.split(':')[0]:int(t.split()[1])*1024 for t in Path('/proc/meminfo').read_text().splitlines()};assert mem['MemAvailable']>=40*1024**3
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(metadata),OPENPLL_KLS_COMPARE_THREADS='4',OPENPLL_KLS_COMPARE_POLICY='application_managed',OPENPLL_PROFILE_EXIT_AFTER_CALLS='64');env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
child=None
try:
 def limits():resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
 command=[str(binary),'-quiet','-o',str(out/'point'),str(point)];start=time.monotonic()
 with (out/'transient.log').open('x') as log:child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
 save(out/'launch.json',dict(pid=child.pid,command=command,automatic_identical_retry=False));save(out/'status.json',dict(state='original_grid_prefix_running',native_pid=child.pid,deadline_uptime=deadline,release_qualified=False))
 code=child.wait(timeout=min(900,max(.001,deadline-60-time.clock_gettime(time.CLOCK_BOOTTIME))));save(out/'receipt.json',dict(exit_code=code,wall_s=time.monotonic()-start));assert code==0
 text=(out/'transient.log').read_text();assert 'OpenPLL_profile_planned_boundary_exit calls=64' in text
 calls=[dict(call=int(a),iterations=int(b),residual=float(v),seconds=float(d),status=int(e)) for a,b,v,d,e in re.findall(r'OpenPLL_wire_PC call=(\d+).*?iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)',text)]
 assert len(calls)==64 and all(x['status']==0 and x['residual']<=1e-12 for x in calls)
 phase=next(t for t in text.splitlines() if t.startswith('solve_profile '));kernel=next(t for t in text.splitlines() if t.startswith('klu_phase_profile '));coarse=[]
 for line in text.splitlines():
  if line.startswith('kls_coarse slot='):
   pairs=dict(re.findall(r'(\w+)=([^ ]+)',line));coarse.append({k:(v if k in ('name','role') else int(v)) for k,v in pairs.items()})
 assert len(coarse)==50 and 'kls_coarse_summary errors=0' in text
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'assessment.json',dict(input_sha256=pins,completed_original_grid_prefix=True,original_deck_byte_identical=True,linear_solves=64,all_logged_full_equation_residual_checks_passed=True,adapter_seconds=sum(x['seconds'] for x in calls),calls=calls,api_phase_profile={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',phase)},vendor_kernel_profile={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',kernel)},coarse_scopes=coarse,completed_full_80ns_transient=False,release_qualified=False))
 save(out/'status.json',dict(state='completed_original_grid_profile',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'failure_receipt.json',dict(error_type=type(e).__name__,message=str(e),release_qualified=False));raise
