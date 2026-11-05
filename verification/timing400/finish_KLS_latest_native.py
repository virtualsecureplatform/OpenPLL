#!/usr/bin/env python3
"""Finish relinks with only API wrappers supplied by upstream diagnostics."""
import json,os,shutil,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];c=root/'build/timing400/release_001/KLS_detailed_profile_001';old=c/'native_build_001';out=c/'native_build_002';out.mkdir(exist_ok=False);(out/'bin').mkdir();deadline=json.loads((c/'owner.json').read_text())['deadline_uptime'];manifest=json.loads((old/'input_manifest.json').read_text());commands=dict(manifest['commands']);shutil.copyfile(old/'bin/Xyce',out/'bin/Xyce')
new=[]
for label in ['link_profile','link_adapter_test']:
 cmd=[x.replace(str(old/'bin'),str(out/'bin')) for x in commands[label] if x!='-Wl,--wrap=kls_solve_transpose'];new.append((label,cmd))
new.extend([('adapter_test',[str(out/'bin/testKLSAdapter')]),('version',[str(out/'bin/Xyce'),'-v'])])
pins={**manifest['input_sha256'],str(old/'input_manifest.json'):digest(old/'input_manifest.json'),str(old/'link_Xyce.log'):digest(old/'link_Xyce.log'),str(Path(__file__).resolve()):digest(Path(__file__).resolve())}
child=None
try:
 for label,command in new:
  save(out/'status.json',dict(state=label,release_qualified=False))
  with (out/(label+'.log')).open('x') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
   code=child.wait(timeout=min(300,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))));assert code==0,label
 assert 'KLS adapter regression passed' in (out/'adapter_test.log').read_text()
 for p,sha in pins.items():assert digest(Path(p))==sha,p
 save(out/'assessment.json',dict(input_sha256=pins,commit='56abf844fb07931370ef386ff724124dfa5d965c',binary=str(out/'bin/Xyce'),binary_sha256=digest(out/'bin/Xyce'),profile_binary=str(out/'bin/Xyce_profile'),profile_binary_sha256=digest(out/'bin/Xyce_profile'),adapter_regression_passed=True,unprovided_transpose_wrapper_removed=True,unused_transpose_API_not_profiled=True,release_qualified=False,adopted=False))
 save(out/'status.json',dict(state='completed_native_relink',release_qualified=False))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
