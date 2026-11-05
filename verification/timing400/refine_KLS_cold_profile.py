#!/usr/bin/env python3
"""Refine deferred cold setup scopes, preserving the prior 50-scope profile."""
import importlib.util,json,os,shlex,shutil,signal,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];out=root/'build/timing400/release_001/KLS_detailed_profile_001';scratch=Path('/tmp/openpll-kls-detailed-20261025-001');source=scratch/'KLS';repo=root/'build/timing400/xyce_kls_sources_003/KLS';deadline=json.loads((out/'owner.json').read_text())['deadline_uptime']
base_tool=out/'profile_tools/prepare_coarse_profile.py';spec=importlib.util.spec_from_file_location('prep',base_tool);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
names=['maybe_promote_auto_metis','maybe_select_pre_static_row_match','maybe_select_auto_row_match','maybe_select_spral_hungarian_row_match','maybe_select_auto_scale','maybe_select_tight_pivot_tolerance','kls_run_deferred_factor_preps','maybe_select_block_structured_ordering','kls_metis_race_take','kls_metis_race_free']
extra={}
for name in names:
 found=[]
 for p in [source/'src/kls.c',*list((source/'src').glob('*.inc'))]:
  try:module.body_start(p.read_text(),name);found.append(p.name)
  except ValueError:pass
 assert len(found)==1,(name,found)
 extra.setdefault(found[0],[]).append((name,'caller'))
tools=out/'refined_tools';tools.mkdir();s=base_tool.read_text();s=s.replace('\ndef body_start','\nfor filename,pairs in '+repr(extra)+'.items():\n    SCOPES.setdefault(filename,[]).extend(pairs)\n\ndef body_start');(tools/'prepare_coarse_profile.py').write_text(s);shutil.copyfile(base_tool.with_name('coarse_profile.inc'),tools/'coarse_profile.inc')
child=None
try:
 command=['python3',str(tools/'prepare_coarse_profile.py'),'--revision','56abf844fb07931370ef386ff724124dfa5d965c','--output',str(scratch/'diagnostic_v3')]
 with (out/'prepare_refined.log').open('x') as log:subprocess.run(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
 diag=scratch/'diagnostic_v3/source'
 for name in ['gklib','metis','scotch','spral']:shutil.copytree(source/'third_party'/name,diag/'third_party'/name,dirs_exist_ok=True)
 shutil.copyfile(scratch/'diagnostic_v3/source-receipt.json',out/'coarse_source_receipt_v3.json')
 entry=next(x for x in json.loads((scratch/'build/compile_commands.json').read_text()) if x['file']==str(source/'src/kls.c'))
 folder=scratch/'refined_member';folder.mkdir();obj=folder/'kls.c.o';cmd=[x.replace(str(source),str(diag)) for x in shlex.split(entry['command'])];cmd[cmd.index('-o')+1]=str(obj)
 save(out/'refined_status.json',dict(state='compiling_deferred_setup_scopes'))
 with (out/'compile_refined.log').open('x') as log:
  child=subprocess.Popen(cmd,cwd=entry['directory'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  code=child.wait(timeout=min(600,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))));assert code==0
 archive=scratch/'libkls_refined.a';shutil.copyfile(scratch/'build/libkls.a',archive);subprocess.run(['ar','r',str(archive),str(obj)],check=True,timeout=30)
 old=scratch/'probe_build_v2/CMakeFiles/compare_coarse_matrix.dir/link.txt';cmd=shlex.split(old.read_text());cmd=[str(archive) if x==str(scratch/'libkls_coarse.a') else x for x in cmd]
 output=cmd.index('-o')+1;cmd[output]=str(scratch/'compare_refined_matrix')
 for i,x in enumerate(cmd):
  p=Path(x)
  if x.endswith('.o') and not p.is_absolute():cmd[i]=str(scratch/'probe_build_v2'/p)
 with (out/'link_refined.log').open('x') as log:subprocess.run(cmd,cwd=scratch/'probe_build_v2',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 save(out/'refined_build_assessment.json',dict(binary=str(scratch/'compare_refined_matrix'),binary_sha256=digest(scratch/'compare_refined_matrix'),scopes=60,inverse_exact=True,source_receipt=str(out/'coarse_source_receipt_v3.json'),input_sha256={str(p):digest(p) for p in [Path(__file__).resolve(),archive,obj,out/'coarse_source_receipt_v3.json',old]}))
 save(out/'refined_status.json',dict(state='compiled_refined_profile'))
except Exception as e:
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 save(out/'refined_build_failure.json',dict(error_type=type(e).__name__,message=str(e)));raise
