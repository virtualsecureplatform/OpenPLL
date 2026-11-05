#!/usr/bin/env python3
"""Add an opt-in diagnostic exit only after a complete true-residual check."""
import json,os,shlex,shutil,subprocess,time
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from build_compact_constant_cap_Xyce import members
root=Path(__file__).resolve().parents[2];c=root/'build/timing400/release_001/KLS_detailed_profile_001';scratch=Path('/tmp/openpll-kls-detailed-20261025-001');xyce=Path('/tmp/openpll-xyce-kls-20261022-001/build');deadline=json.loads((c/'owner.json').read_text())['deadline_uptime'];out=c/'native_boundary_build_001';out.mkdir(exist_ok=False)
prior=root/'build/timing400/release_001/KLS_certification_comparison_001/native_source_002'
header=(prior/'OpenPLL_KLS_comparison.h').read_text();needle='        return code;\n    }\n};'
assert header.count(needle)==1
addition='''        // Diagnostic-only process exit at a completed, accepted solve boundary.
        const char* exit_after=std::getenv("OPENPLL_PROFILE_EXIT_AFTER_CALLS");
        if(exit_after && std::string(exit_after)=="64" && calls_>=64 && code==0) {
            std::cout << "OpenPLL_profile_planned_boundary_exit calls=" << calls_ << std::endl;
            std::exit(0);
        }
'''
newheader=header.replace(needle,addition+needle);assert newheader.replace(addition,'')==header
(out/'OpenPLL_KLS_boundary_profile.h').write_text(newheader);source=out/'N_LAS_KLSSolver.C';source.write_text((prior/'N_LAS_KLSSolver.C').read_text().replace('OpenPLL_KLS_comparison.h','OpenPLL_KLS_boundary_profile.h'))
options={}
for line in (xyce/'src/CMakeFiles/XyceLib.dir/flags.make').read_text().splitlines():
 if ' = ' in line:
  k,v=line.split(' = ',1);options[k]=shlex.split(v)
options['CXX_INCLUDES']=[x.replace('/tmp/openpll-xyce-kls-20261022-001/KLS/include',str(scratch/'KLS/include')) for x in options['CXX_INCLUDES']]
obj=out/'N_LAS_KLSSolver.C.o';compilecmd=['g++',*options['CXX_DEFINES'],*options['CXX_INCLUDES'],*options['CXX_FLAGS'],'-c',str(source),'-o',str(obj)]
archive=scratch/'libxyce_boundary.a';shutil.copyfile(scratch/'libxyce_latest.a',archive)
command=dict(json.loads((c/'native_build_001/input_manifest.json').read_text())['commands'])['link_profile'];command=[str(archive) if x==str(scratch/'libxyce_latest.a') else x for x in command if x!='-Wl,--wrap=kls_solve_transpose'];command[command.index('-o')+1]=str(out/'Xyce_profile')
for label,cmd in [('compile',compilecmd),('archive',['ar','r',str(archive),str(obj)]),('link',command)]:
 with (out/(label+'.log')).open('x') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=min(180,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
a,b=members(scratch/'libxyce_latest.a'),members(archive);assert a.keys()==b.keys();assert [k for k in a if a[k]!=b[k]]==['N_LAS_KLSSolver.C.o']
save(out/'assessment.json',dict(binary=str(out/'Xyce_profile'),binary_sha256=digest(out/'Xyce_profile'),mathematical_solver_code_unchanged_before_exit=True,only_archive_member_changed='N_LAS_KLSSolver.C.o',planned_exit_after_full_true_residual_checked_calls=64,input_sha256={str(p):digest(p) for p in [Path(__file__).resolve(),source,out/'OpenPLL_KLS_boundary_profile.h',prior/'OpenPLL_KLS_comparison.h',archive]},release_qualified=False))
