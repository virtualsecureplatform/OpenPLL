#!/usr/bin/env python3
"""Build a pinned updated KLS in isolation within the comparison budget."""
import json,os,resource,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_certification_comparison_001'
scratch=Path('/tmp/openpll-kls-certification-20261024-001');deadline=json.loads((out/'owner.json').read_text())['deadline_uptime']
pins={str(p):digest(p) for p in (Path(__file__).resolve(),out/'owner.json',out/'KLS_source.tar')}
commands=[('configure',['cmake','-S',str(scratch/'KLS'),'-B',str(scratch/'build'),'-DCMAKE_BUILD_TYPE=Release','-DKLS_BUILD_TESTS=ON','-DKLS_BUILD_BENCHMARKS=OFF','-DKLS_BUILD_AUTOTUNER=OFF']),('build',['cmake','--build',str(scratch/'build'),'-j4'])]
child=None
try:
 for label,command in commands:
  save(out/'build_status.json',dict(state=label,release_qualified=False))
  with (out/(label+'.log')).open('x') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
   code=child.wait(timeout=max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
  assert code==0,label
 for p in (scratch/'build').rglob('*.a'):pins[str(p)]=digest(p)
 save(out/'build_assessment.json',dict(updated_KLS_built=True,commit='7d2c909c6ab77a7201bad8559b024f4e97625840',input_sha256=pins,release_qualified=False))
 save(out/'build_status.json',dict(state='completed_build',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'build_failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
