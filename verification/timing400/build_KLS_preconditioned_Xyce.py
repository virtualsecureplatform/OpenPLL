#!/usr/bin/env python3
"""Build a one-object map-correction patch; preserve unmodified fork failure."""
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from build_compact_constant_cap_Xyce import members

root=Path(__file__).resolve().parents[2];campaign=root/'build/timing400/release_001/KLS_preconditioner_001'
owner=json.loads((campaign/'owner.json').read_text());deadline=owner['deadline_uptime']
scratch=Path('/tmp/openpll-xyce-kls-20261022-001');build=scratch/'build'
source=campaign/'source_001';source.mkdir(exist_ok=False)
original=root/'build/timing400/release_001/fork_Xyce_KLS_001/adapter_fix_source_001/N_LAS_KLSSolver.C'
header=root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_KLS_reuse_bounded.h'
proof=root/'build/timing400/release_001/native_KLS_reuse_probe_checks_001/assessment.json'
assert json.loads(proof.read_text())['all_original_equation_residual_checks_passed']
text=original.read_text()
text='#include "'+header.name+'"\n'+text
needle='int KLSSolver::doSolve(bool reuse_factors, bool transpose)\n{'
assert text.count(needle)==1
text=text.replace(needle,needle+'\n  if (std::getenv("OPENPLL_WIRE_PC")) return OpenPLLWireKLSReusePC::solve(*problem_,transpose);')
(source/'N_LAS_KLSSolver.C').write_text(text);shutil.copyfile(header,source/header.name)
(source/'column_map_fix.patch').write_text('Inherited published column-map fix; opt-in KLS-preconditioned GMRES added.\n')
out=campaign/'build_001';out.mkdir(exist_ok=False);(out/'bin').mkdir()
old_archive=build/'src/libxyce.a';archive=scratch/'libxyce_KLS_preconditioner.a'
shutil.copyfile(old_archive,archive)
flags=build/'src/CMakeFiles/XyceLib.dir/flags.make';options={}
for line in flags.read_text().splitlines():
    if ' = ' in line:
        k,v=line.split(' = ',1);options[k]=shlex.split(v)
obj=source/'N_LAS_KLSSolver.C.o'
compile_command=['/usr/bin/g++',*options['CXX_DEFINES'],*options['CXX_INCLUDES'],*options['CXX_FLAGS'],
                 '-c',str(source/'N_LAS_KLSSolver.C'),'-o',str(obj)]
def link_command(linkfile,destination):
    command=shlex.split(linkfile.read_text());output=command.index('-o')+1
    for i,token in enumerate(command):
        if i==output:continue
        p=Path(token)
        if not p.is_absolute():p=linkfile.parent.parents[1]/p
        # Each link.txt lives in CMakeFiles/<target>.dir under the target cwd.
        if p.resolve()==old_archive.resolve():command[i]=str(archive)
        elif p.is_file():command[i]=str(p)
    command[output]=str(destination);return command
xyce_link=build/'src/CMakeFiles/Xyce.dir/link.txt'
test_link=build/'src/test/LinearAlgebraTest/CMakeFiles/testKLSAdapter.dir/link.txt'
commands=[('compile',compile_command),('archive',['ar','r',str(archive),str(obj)]),
          ('link_Xyce',link_command(xyce_link,out/'bin/Xyce')),
          ('link_adapter_test',link_command(test_link,out/'bin/testKLSAdapter')),
          ('adapter_test',[str(out/'bin/testKLSAdapter')]),('version',[str(out/'bin/Xyce'),'-v'])]
pins={str(p):digest(p) for p in [Path(__file__).resolve(),source/'N_LAS_KLSSolver.C',
      source/header.name,source/'column_map_fix.patch',old_archive,flags,xyce_link,test_link,
      original,header,proof,campaign/'owner.json']}
for _,command in commands:
    for token in command:
        p=Path(token)
        if p.is_absolute() and p.is_file() and p not in (archive,obj) and not p.is_relative_to(out):pins[str(p)]=digest(p)
save(out/'owner.json',dict(runner_pid=os.getpid(),deadline_uptime=deadline,budget_restarted=False,
     original_fork_failure_retained=True,source_patch=str(source/'column_map_fix.patch')))
save(out/'input_manifest.json',dict(input_sha256=pins,commands=commands))
child=None;receipts=[]
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def limits():resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
try:
    for label,command in commands:
        assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline-300
        started=time.monotonic()
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=build/'src',stdout=log,stderr=subprocess.STDOUT,
                 start_new_session=True,preexec_fn=limits,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            save(out/'status.json',dict(state=label,runner_pid=os.getpid(),child_pid=child.pid,release_qualified=False))
            code=child.wait(timeout=min(300,deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME)))
        receipts.append(dict(stage=label,exit_code=code,elapsed_s=time.monotonic()-started))
        save(out/'stage_receipts.json',receipts);assert code==0,label
    assert 'KLS adapter regression passed' in (out/'adapter_test.log').read_text()
    original,changed=members(old_archive),members(archive)
    assert original.keys()==changed.keys()
    differences=[name for name in original if original[name]!=changed[name]]
    assert differences==['N_LAS_KLSSolver.C.o']
    assert changed[differences[0]]==digest(obj)
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    save(out/'assessment.json',dict(fork_Xyce_KLS_build_passed=True,binary=str(out/'bin/Xyce'),
         binary_sha256=digest(out/'bin/Xyce'),input_sha256=pins,adapter_regression_passed=True,
         source_code_modified=True,patch_scope='published column map fix plus opt-in KLS sparse preconditioner and full-equation GMRES',
         source_patch=str(source/'column_map_fix.patch'),changed_archive_members=differences,
         unchanged_archive_members=len(original)-1,original_fork_failure_retained=True,
         KLS_library_modified=False,native_waveform_controls_passed=False,
         release_qualified=False,adopted=False))
    save(out/'status.json',dict(state='built_adapter_regression_passed_controls_pending',release_qualified=False))
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False));raise
finally:stop()
