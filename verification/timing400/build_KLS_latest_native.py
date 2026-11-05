#!/usr/bin/env python3
"""Relink the unchanged tested Xyce adapter against current pinned KLS."""
import json,os,shutil,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';campaign=base/'KLS_detailed_profile_001';deadline=json.loads((campaign/'owner.json').read_text())['deadline_uptime'];scratch=Path('/tmp/openpll-kls-detailed-20261025-001')
assert json.loads((campaign/'profile_assessment.json').read_text())['independent_full_equation_checks_passed']==159
previous=base/'KLS_certification_comparison_001/native_build_002';manifest=json.loads((previous/'input_manifest.json').read_text());prior=json.loads((previous/'assessment.json').read_text());assert prior['adapter_regression_passed']
old=Path('/tmp/openpll-kls-certification-20261024-001');assert digest(old/'KLS/include/kls/kls.h')==digest(scratch/'KLS/include/kls/kls.h')
out=campaign/'native_build_001';out.mkdir(exist_ok=False);(out/'bin').mkdir();archive=scratch/'libxyce_latest.a';shutil.copyfile(old/'libxyce_optout_002.a',archive)
wraps='kls_analyze_csr kls_factor kls_refactor kls_solve kls_solve_transpose kls_refactor_solve kls_componentwise_certify_correction trilinos_klu_l_factor trilinos_klu_l_refactor trilinos_klu_l_solve trilinos_klu_l_tsolve malloc calloc realloc free aligned_alloc posix_memalign'.split()
original=dict(manifest['commands'])
def link(command,destination,profile=False):
 result=[]
 for token in command:
  if token==str(old/'libxyce_optout_002.a'):token=str(archive)
  elif token.startswith(str(old/'build/')):token=token.replace(str(old/'build'),str(scratch/'build'),1)
  result.append(token)
 result[result.index('-o')+1]=str(destination)
 if profile:
  result=[str(scratch/'libkls_coarse.a') if token==str(scratch/'build/libkls.a') else token for token in result]
  result[1:1]=[str(scratch/'phase_legacy.o'),*['-Wl,--wrap='+name for name in wraps]]
 return result
commands=[('link_Xyce',link(original['link_Xyce'],out/'bin/Xyce')),('link_profile',link(original['link_Xyce'],out/'bin/Xyce_profile',True)),('link_adapter_test',link(original['link_adapter_test'],out/'bin/testKLSAdapter')),('adapter_test',[str(out/'bin/testKLSAdapter')]),('version',[str(out/'bin/Xyce'),'-v'])]
pins={str(p):digest(p) for p in [Path(__file__).resolve(),campaign/'owner.json',campaign/'profile_assessment.json',previous/'input_manifest.json',previous/'assessment.json',archive]}
for _,command in commands:
 for token in command:
  p=Path(token)
  if p.is_absolute() and p.is_file() and not p.is_relative_to(out):pins[str(p)]=digest(p)
save(out/'input_manifest.json',dict(input_sha256=pins,commands=commands,unchanged_adapter_and_public_ABI=True));child=None;receipts=[]
try:
 for label,command in commands:
  save(out/'status.json',dict(state=label,release_qualified=False))
  start=time.monotonic()
  with (out/(label+'.log')).open('x') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
   code=child.wait(timeout=min(300,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
  receipts.append(dict(stage=label,exit_code=code,wall_s=time.monotonic()-start));save(out/'receipts.json',receipts);assert code==0,label
 assert 'KLS adapter regression passed' in (out/'adapter_test.log').read_text()
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'assessment.json',dict(input_sha256=pins,commit='56abf844fb07931370ef386ff724124dfa5d965c',binary=str(out/'bin/Xyce'),binary_sha256=digest(out/'bin/Xyce'),profile_binary=str(out/'bin/Xyce_profile'),profile_binary_sha256=digest(out/'bin/Xyce_profile'),adapter_regression_passed=True,release_qualified=False,adopted=False))
 save(out/'status.json',dict(state='completed_native_relink',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
