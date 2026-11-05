#!/usr/bin/env python3
"""Resolve deferred setup timings on the independently checked captured graph."""
import fcntl,json,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest,save
from audit_KLS_profile_equations import audit
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';out=base/'KLS_detailed_profile_001';scratch=Path('/tmp/openpll-kls-detailed-20261025-001');deadline=json.loads((out/'owner.json').read_text())['deadline_uptime'];proof=json.loads((out/'refined_build_assessment.json').read_text());binary=Path(proof['binary']);assert digest(binary)==proof['binary_sha256']
folder=out/'refined_managed_matrix';folder.mkdir(exist_ok=False);inputs=base/'native_adapter_probe_inputs_001'
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not live_engines()
child=None
try:
 def limits():resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
 command=[str(binary),str(inputs),str(folder),'KLS'];start=time.monotonic()
 with (folder/'native.log').open('x') as log:
  child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(base/'native_wire_preconditioner_metadata_001/wire_C.bin'),OPENPLL_KLS_COMPARE_THREADS='4',OPENPLL_KLS_COMPARE_POLICY='application_managed'))
  save(folder/'launch.json',dict(pid=child.pid,command=command));code=child.wait(timeout=min(180,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
 save(folder/'receipt.json',dict(exit_code=code,wall_s=time.monotonic()-start));assert code==0
 original=load_npz(base/'DCO_native_linear_system_capture_002/native_Jacobian.npz').tocsr();n=original.shape[0];diag=np.flatnonzero(original.indices==np.repeat(np.arange(n),np.diff(original.indptr)))
 report=audit((folder/'native.log').read_text(),folder,'matrix','KLS_managed_4t','coarse','refined_managed_matrix','4','application_managed',60,original,n,diag,None,None,lambda:deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
 report['input_sha256']={str(p):digest(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('audit_KLS_profile_equations.py'),out/'refined_build_assessment.json',binary,base/'DCO_native_linear_system_capture_002/native_Jacobian.npz',base/'native_wire_preconditioner_metadata_001/wire_C.bin']}
 save(folder/'assessment.json',report);print(json.dumps([(v['name'],v['inclusive_ns']/1e9) for v in sorted(report['coarse_scopes'],key=lambda x:x['api_exclusive_ns'],reverse=True)[:10]]))
finally:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
