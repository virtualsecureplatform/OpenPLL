#!/usr/bin/env python3
"""Short diagnostic native prefix; retain physical deck and exact residual gate."""
import fcntl,json,os,re,resource,signal,subprocess,time,statistics
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';campaign=base/'KLS_certification_comparison_001'
deadline=json.loads((campaign/'owner.json').read_text())['deadline_uptime'];selected=json.loads((campaign/'selected_candidate.json').read_text())
proof=campaign/'optout_native_controls_001/assessment.json';assert json.loads(proof.read_text())['native_waveform_controls_passed']
built=json.loads((campaign/'native_build_002/assessment.json').read_text());binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
source=base/'KLS_preconditioner_001/DCO_nom_tt27_c0_f247_80ns_001/point.cir'
metadata=base/'native_wire_preconditioner_metadata_001/wire_C.bin';namesref=base/'DCO_bounded_reuse_variable_map_001/candidate.names'
priorlog=base/'KLS_preconditioner_001/DCO_nom_tt27_c0_f247_80ns_001/transient.log'
out=campaign/'optout_native_prefix_001';out.mkdir(exist_ok=False);deck=out/'point.cir'
deck.write_text(source.read_text().replace('KLS_THREADS=4','KLS_THREADS='+str(selected['threads'])))
pins={str(p):digest(p) for p in [Path(__file__).resolve(),campaign/'owner.json',campaign/'selected_candidate.json',proof,campaign/'native_build_002/assessment.json',source,deck,binary,metadata,namesref]}
inherited=source.parent/'input_manifest.json'
pins.update(json.loads(inherited.read_text())['input_sha256'])
pins[str(inherited)]=digest(inherited)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'input_manifest.json',dict(input_sha256=pins,planned_completed_solver_calls=64,transient_wall_limit_s=600,full_transient_qualification=False))
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not live_engines()
mem={t.split(':')[0]:int(t.split()[1])*1024 for t in Path('/proc/meminfo').read_text().splitlines()};assert mem['MemAvailable']>=40*1024**3
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(metadata),OPENPLL_KLS_COMPARE_THREADS=str(selected['threads']),OPENPLL_KLS_COMPARE_POLICY='application_managed');env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
child=None
def limits():resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
def stop():
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def names(p):
 a={int(t.split()[0]):t.split()[1].upper() for t in p.read_text().splitlines()[1:]};assert set(a)==set(range(len(a)));return a
def calls(text):return [dict(call=int(a),iterations=int(b),residual=float(c),seconds=float(d),status=int(e)) for a,b,c,d,e in re.findall(r'OpenPLL_wire_PC call=(\d+).*?iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)',text)]
try:
 for stage in ['variable_map','transient']:
  command=[str(binary),'-quiet']+(['-namesfile',str(out/'candidate.names')] if stage=='variable_map' else ['-o',str(out/'point')])+[str(deck)]
  start=time.monotonic();stage_deadline=min(deadline-60,time.clock_gettime(time.CLOCK_BOOTTIME)+(600 if stage=='transient' else 900))
  with (out/(stage+'.log')).open('x') as log:child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
  save(out/(stage+'_launch.json'),dict(pid=child.pid,command=command,automatic_identical_retry=False))
  save(out/'status.json',dict(state=stage+'_running',native_pid=child.pid,deadline_uptime=deadline,release_qualified=False))
  reason=None
  while child.poll() is None:
   if time.clock_gettime(time.CLOCK_BOOTTIME)>=stage_deadline:reason='planned_stage_wall_limit';stop();break
   if stage=='transient':
    records=calls((out/'transient.log').read_text())
    if len(records)>=64:reason='planned_completed_call_count';stop();break
    if any(v['status'] or v['residual']>1e-12 for v in records):reason='linear_solve_nonpass';stop();break
   time.sleep(1)
  save(out/(stage+'_receipt.json'),dict(exit_code=child.returncode,wall_s=time.monotonic()-start,stop_reason=reason))
  if stage=='variable_map':assert child.returncode==0 and names(out/'candidate.names')==names(namesref)
 records=calls((out/'transient.log').read_text());assert records and all(v['status']==0 and v['residual']<=1e-12 for v in records)
 previous=calls(priorlog.read_text());pairs=list(zip(previous[:len(records)],records))
 aligned=all(a['call']==b['call'] and a['iterations']==b['iterations'] for a,b in pairs)
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'assessment.json',dict(input_sha256=pins,selected_candidate=selected,completed_solver_calls=len(records),all_logged_true_residual_checks_passed=True,original_full_equation_limit=1e-12,stop_reason=reason,records=records,comparison_same_call_numbers_and_iteration_counts=aligned,previous_KLS_certified_prefix_adapter_seconds=sum(a['seconds'] for a,b in pairs),candidate_prefix_adapter_seconds=sum(b['seconds'] for a,b in pairs),historical_comparison_not_controlled_same_session=True,full_DCO_speedup_demonstrated=False,full_transient_qualification=False,release_qualified=False))
 save(out/'status.json',dict(state='completed_diagnostic_prefix',release_qualified=False))
except Exception as e:
 stop();save(out/'failure_receipt.json',dict(error_type=type(e).__name__,message=str(e)));raise
finally:stop()
