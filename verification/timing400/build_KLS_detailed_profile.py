#!/usr/bin/env python3
"""Pin updated KLS and build uninstrumented plus reversible diagnostic archives."""
import json,os,shlex,shutil,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_detailed_profile_001';deadline=json.loads((out/'owner.json').read_text())['deadline_uptime']
scratch=Path('/tmp/openpll-kls-detailed-20261025-001');scratch.mkdir(exist_ok=False);source=scratch/'KLS';source.mkdir();repo=root/'build/timing400/xyce_kls_sources_002/KLS';revision='56abf844fb07931370ef386ff724124dfa5d965c'
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
 run('archive',['git','-C',str(repo),'archive','--format=tar','-o',str(out/'KLS_source.tar'),revision])
 run('extract',['tar','xf',str(out/'KLS_source.tar'),'-C',str(source)])
 old=Path('/tmp/openpll-kls-certification-20261024-001/KLS')
 for name in ['gklib','metis','scotch','spral']:
  expected=subprocess.check_output(['git','-C',str(repo),'rev-parse',revision+':third_party/'+name],text=True).strip()
  previous=subprocess.check_output(['git','-C',str(repo),'rev-parse','7d2c909:third_party/'+name],text=True).strip();assert previous==expected
  shutil.copytree(old/'third_party'/name,source/'third_party'/name,dirs_exist_ok=True)
 run('prepare_coarse',['python3',str(repo/'scripts/prepare_coarse_profile.py'),'--revision',revision,'--output',str(scratch/'diagnostic')],repo)
 diag=scratch/'diagnostic/source'
 for name in ['gklib','metis','scotch','spral']:shutil.copytree(source/'third_party'/name,diag/'third_party'/name,dirs_exist_ok=True)
 shutil.copyfile(scratch/'diagnostic/source-receipt.json',out/'coarse_source_receipt.json')
 run('configure',['cmake','-S',str(source),'-B',str(scratch/'build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG -g','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DKLS_BUILD_TESTS=ON','-DKLS_BUILD_BENCHMARKS=OFF','-DKLS_BUILD_AUTOTUNER=OFF'])
 run('build',['cmake','--build',str(scratch/'build'),'--target','kls','kls_smoke','kls_application_managed','kls_componentwise','klu_allocator_ownership','-j4'])
 commands=json.loads((scratch/'build/compile_commands.json').read_text());entry=next(x for x in commands if x['file']==str(source/'src/kls.c'))
 cmd=shlex.split(entry['command']);obj=scratch/'kls_coarse.c.o';cmd=[x.replace(str(source),str(diag)) for x in cmd];cmd[cmd.index('-o')+1]=str(obj)
 run('compile_coarse',cmd,entry['directory'])
 archive=scratch/'libkls_coarse.a';shutil.copyfile(scratch/'build/libkls.a',archive)
 # Preserve the archive member name so the diagnostic replaces, rather than adds to, kls.c.o.
 member=scratch/'coarse_member';member.mkdir();shutil.copyfile(obj,member/'kls.c.o')
 run('archive_coarse',['ar','r',str(archive),str(member/'kls.c.o')])
 for name,src,extra in [('phase',source/'bench/kls_klu_phase_profile.c',['-DKLS_PROFILE_VERDICT_INTERFACE']),('cpu',source/'scripts/profile_cpu_samples.c',[])]:
  command=['gcc','-O3','-g','-I'+str(source/'include'),'-I'+str(source/'src'),'-I'+str(source/'third_party/suitesparse/KLU/Include'),'-I'+str(source/'third_party/suitesparse/UFconfig'),*extra,'-c',str(src),'-o',str(scratch/(name+'.o'))]
  run('compile_'+name,command)
 run('controls',['ctest','--test-dir',str(scratch/'build'),'--output-on-failure','-R','^(kls_smoke|kls_application_managed|kls_componentwise|klu_allocator_ownership)$','--timeout','90'])
 pins={str(p):digest(p) for p in [Path(__file__).resolve(),out/'owner.json',out/'KLS_source.tar',out/'coarse_source_receipt.json',scratch/'build/compile_commands.json',archive,scratch/'phase.o',scratch/'cpu.o',*list((scratch/'build').rglob('*.a'))]}
 save(out/'build_assessment.json',dict(updated_KLS_built=True,commit=revision,unmodified_release_library=str(scratch/'build/libkls.a'),diagnostic_archive=str(archive),instrumentation_inverse_exact=True,source_modified_only_for_diagnostics=True,upstream_controls_passed=4,input_sha256=pins))
 save(out/'build_status.json',dict(state='completed_normal_and_diagnostic_builds',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'build_failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
