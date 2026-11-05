#!/usr/bin/env python3
"""Pin updated KLS and build uninstrumented plus reversible diagnostic archives."""
import json,os,shlex,shutil,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_detailed_profile_001';deadline=json.loads((out/'owner.json').read_text())['deadline_uptime']
scratch=Path('/tmp/openpll-kls-detailed-20261025-001');source=scratch/'KLS';repo=root/'build/timing400/xyce_kls_sources_002/KLS';revision='56abf844fb07931370ef386ff724124dfa5d965c'
child=None;receipts=[]
def run(label,command,cwd=None):
 global child
 start=time.monotonic();remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert remaining>0
 save(out/'build_status.json',dict(state=label,release_qualified=False))
 with (out/(label+'.log')).open('x') as log:
  child=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
  code=child.wait(timeout=min(900,remaining))
 receipts.append(dict(stage=label,exit_code=code,wall_s=time.monotonic()-start));save(out/'build_receipts.json',receipts);assert code==0,label
try:
 for name,src,extra in [('phase',source/'bench/kls_klu_phase_profile.c',['-DKLS_PROFILE_VERDICT_INTERFACE']),('cpu',source/'scripts/profile_cpu_samples.c',[])]:
  includes=[source/'include',source/'src',source/'third_party/suitesparse/UFconfig',*list((source/'third_party/suitesparse').glob('*/Include'))]
  command=['gcc','-O3','-g',*['-I'+str(p) for p in includes],*extra,'-c',str(src),'-o',str(scratch/(name+'.o'))]
  run('compile_'+name+'_complete',command)
 run('controls',['ctest','--test-dir',str(scratch/'build'),'--output-on-failure','-R','^(kls_smoke|kls_application_managed|kls_componentwise|kls_klu_allocator_ownership)$','--timeout','90'])
 pins={str(p):digest(p) for p in [Path(__file__).resolve(),out/'owner.json',out/'KLS_source.tar',out/'coarse_source_receipt_v2.json',scratch/'build/compile_commands.json',scratch/'libkls_coarse.a',scratch/'phase.o',scratch/'cpu.o',*list((scratch/'build').rglob('*.a'))]}
 save(out/'build_assessment.json',dict(updated_KLS_built=True,commit=revision,unmodified_release_library=str(scratch/'build/libkls.a'),diagnostic_archive=str(scratch/'libkls_coarse.a'),instrumentation_inverse_exact=True,source_modified_only_for_diagnostics=True,upstream_controls_passed=4,input_sha256=pins))
 save(out/'build_status.json',dict(state='completed_normal_and_diagnostic_builds',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'finish_build_failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
