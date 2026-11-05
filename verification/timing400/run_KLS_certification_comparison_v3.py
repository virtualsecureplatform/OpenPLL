#!/usr/bin/env python3
"""Matched KLU/KLS policy/thread comparison with independent full-A checks."""
import fcntl,json,os,random,re,resource,signal,subprocess,time,statistics,shlex
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';out=base/'KLS_certification_comparison_001'
owner=json.loads((out/'owner.json').read_text());deadline=owner['deadline_uptime'];scratch=Path('/tmp/openpll-kls-certification-20261024-001')
proof=json.loads((out/'build_assessment.json').read_text());assert proof['updated_KLS_built']
source=Path(__file__).with_name('native_KLS_certification_comparison_v2');build=scratch/'probe_build_v2';inputs=base/'native_adapter_probe_inputs_001';metadata=base/'native_wire_preconditioner_metadata_001/wire_C.bin'
pins={**proof['input_sha256'],str(out/'build_assessment.json'):digest(out/'build_assessment.json')}
for p in [Path(__file__).resolve(),metadata,inputs/'original_A.bin',inputs/'native_Newton_RHS.bin',inputs/'known_solution.bin',base/'DCO_native_linear_system_capture_002/native_Jacobian.npz',*source.iterdir()]:pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'comparison_input_manifest_v3.json',dict(input_sha256=pins))
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not live_engines()
child=None;envbase=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(metadata))
def remaining():
 value=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
 if value<=0:raise TimeoutError('one-hour comparison deadline')
 return value
def limits():resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
def run(label,command,folder,env=None,timeout=600):
 global child
 folder.mkdir(exist_ok=True)
 if (folder/'receipt.json').exists():
  receipt=json.loads((folder/'receipt.json').read_text());launch=json.loads((folder/'launch.json').read_text())
  assert receipt['exit_code']==0 and launch['command']==command
  pins[str(folder/'native.log')]=digest(folder/'native.log')
  return (folder/'native.log').read_text()
 save(out/'comparison_status.json',dict(state=label,release_qualified=False))
 start=time.monotonic()
 with (folder/'native.log').open('x') as log:
  child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits,env=env or envbase)
  save(folder/'launch.json',dict(pid=child.pid,command=command,automatic_identical_retry=False))
  code=child.wait(timeout=min(timeout,remaining()))
 save(folder/'receipt.json',dict(exit_code=code,wall_s=time.monotonic()-start));assert code==0,label
 return (folder/'native.log').read_text()
def stop():
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
try:
 run('configure_probe',['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release','-DTrilinos_DIR='+str(base/'stock_serial_Xyce_001/trilinos-install/lib/cmake/Trilinos')],out/'probe_configure_v2')
 run('build_probe',['cmake','--build',str(build),'--target','compare_matrix','-j2'],out/'probe_build_v2')
 for p in [*build.glob('compare_*'),scratch/'probe_build/compare_rhs']:pins[str(p)]=digest(p)
 for link in build.glob('CMakeFiles/compare_*.dir/link.txt'):
  pins[str(link)]=digest(link)
  for token in shlex.split(link.read_text()):
   p=Path(token)
   if p.is_absolute() and p.is_file():pins[str(p)]=digest(p)
 # Exercise existing upstream policy/API/certificate tests, not the entire unrelated suite.
 run('upstream_policy_controls',['ctest','--test-dir',str(scratch/'build'),'--output-on-failure','-R','^(kls_smoke|kls_application_managed|kls_componentwise|kls_componentwise_faults|kls_original_operator_cache|kls_componentwise_parallel|kls_componentwise_team)$','--timeout','90'],out/'upstream_controls',timeout=600)
 A=load_npz(base/'DCO_native_linear_system_capture_002/native_Jacobian.npz').tocsr();n=A.shape[0]
 diag=np.flatnonzero(A.indices==np.repeat(np.arange(n),np.diff(A.indptr)));original=A.copy()
 native_rhs=np.fromfile(inputs/'native_Newton_RHS.bin',dtype='<f8');known_rhs=np.fromfile(inputs/'known_solution.bin',dtype='<f8')
 variants=[('KLU',None,None),('KLS_certified_1t','1','certified'),('KLS_certified_4t','4','certified'),('KLS_managed_1t','1','application_managed'),('KLS_managed_4t','4','application_managed')]
 rng=random.Random(20261024);reports=[]
 for repeat in range(3):
  order=variants.copy();rng.shuffle(order)
  for variant,threads,policy in order:
   for kind in ['rhs','matrix']:
    folder=out/(f'repeat{repeat}_{variant}_{kind}'+('_v2' if kind=='matrix' else ''));env=dict(envbase)
    if threads:env.update(OPENPLL_KLS_COMPARE_THREADS=threads,OPENPLL_KLS_COMPARE_POLICY=policy)
    text=run('running_'+folder.name,[str((scratch/'probe_build/compare_rhs') if kind=='rhs' else build/'compare_matrix'),str(inputs),str(folder),'KLU' if variant=='KLU' else 'KLS'],folder,env,timeout=180)
    cases=[json.loads(line) for line in text.splitlines() if line.startswith('{')];assert len(cases)==(5 if kind=='rhs' else 8)
    totals=re.findall(r'OpenPLL_inner_totals calls=(\d+) seconds=(\S+)',text);assert len(totals)==1
    if threads:assert f'threads={threads} policy={policy}' in text
    checks=[]
    for case in cases:
     remaining();label=case['case'];solution=np.fromfile(folder/(label+'.bin'),dtype='<f8');rhs=np.fromfile(folder/(label+'.rhs.bin'),dtype='<f8')
     assert case['original_Jacobian_unchanged'] and case['original_RHS_unchanged'];assert solution.shape==rhs.shape==(n,) and np.isfinite(solution).all()
     M=original.copy()
     if kind=='matrix':
      step=int(label.rsplit('step',1)[1]);delta=[0,1e-8,1e-6,1e-4,.01,0,.01,0][step]
      M.data[diag]+=delta*abs(M.data[diag]);
      if step==6:M.data*=2
      known=.1*(np.sin(.013*np.arange(n)+.0001*step)+np.cos(.027*np.arange(n)))
      expected=M@known;terms=np.diff(M.indptr);eps=np.finfo(float).eps;bound=8*(terms*eps/(1-terms*eps))*(abs(M)@abs(known))+8*eps*abs(expected)
      assert np.all(abs(rhs-expected)<=bound);assert max(abs(solution-known))<1e-7
     else:
      expected=known_rhs if label.endswith(('known_solution','known_repeat')) else native_rhs.copy()
      if label.endswith('perturbed_native'):
       scale=1/np.asarray(abs(M).max(axis=1).toarray()).ravel()
       expected+=.001*np.linalg.norm(scale*native_rhs)/np.linalg.norm(scale*known_rhs)*known_rhs
      if label.endswith('perturbed_native'):
       perturbation=expected-native_rhs
       eps=np.finfo(float).eps
       bound=8*n*eps*abs(perturbation)+8*eps*(abs(native_rhs)+abs(perturbation))
       assert np.all(abs(rhs-expected)<=bound)
      else:assert np.array_equal(rhs,expected)
     scale=1/np.asarray(abs(M).max(axis=1).toarray()).ravel();relative=float(np.linalg.norm(scale*(M@solution-rhs))/np.linalg.norm(scale*rhs));assert relative<=1e-12
     checks.append(dict(case=label,weighted_original_equation_residual=relative,solve_wall_s=case['solve_wall_s']))
    report=dict(repeat=repeat,variant=variant,kind=kind,checks=checks,solve_total_s=sum(v['solve_wall_s'] for v in cases),inner_calls=int(totals[0][0]),inner_seconds=float(totals[0][1]),stale_factor_recovery_exercised='OpenPLL_wire_factor_refresh_after_nonpass' in text)
    reports.append(report);save(folder/'assessment.json',report);save(out/'comparison_results.json',reports)
 summary=[]
 for variant,_,_ in variants:
  r=[x for x in reports if x['variant']==variant]
  summary.append(dict(variant=variant,rhs_median_total_s=statistics.median(x['solve_total_s'] for x in r if x['kind']=='rhs'),matrix_median_total_s=statistics.median(x['solve_total_s'] for x in r if x['kind']=='matrix'),rhs_median_inner_s=statistics.median(x['inner_seconds'] for x in r if x['kind']=='rhs'),matrix_median_inner_s=statistics.median(x['inner_seconds'] for x in r if x['kind']=='matrix')))
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'comparison_assessment.json',dict(input_sha256=pins,summary=summary,independent_full_equation_checks_passed=sum(len(x['checks']) for x in reports),all_variants_same_outer_solver=True,randomized_variant_order=True,repetitions=3,full_DCO_speedup_demonstrated=False,release_qualified=False))
 save(out/'comparison_status.json',dict(state='completed_matched_comparison',release_qualified=False));print(json.dumps(summary))
except Exception as e:
 stop();save(out/'comparison_failure_v3.json',dict(error_type=type(e).__name__,message=str(e)));save(out/'comparison_status.json',dict(state='comparison_nonpass',release_qualified=False));raise
finally:stop()
