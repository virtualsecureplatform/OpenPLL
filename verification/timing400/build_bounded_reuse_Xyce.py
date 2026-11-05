#!/usr/bin/env python3
"""Recompile one adapter into a copied archive; preserve all live build inputs."""
from datetime import datetime,timezone
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

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
proof=base/'native_bounded_reuse_probe_checks_001/assessment.json'
assert json.loads(proof.read_text())['all_original_equation_residual_checks_passed']
owner=json.loads((base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002/owner.json').read_text())
# Inherit the active DCO experiment deadline, including all preparation.
deadline=min(time.clock_gettime(time.CLOCK_BOOTTIME)+600,owner['deadline_uptime'])
out=base/'wire_preconditioned_Xyce_bounded_reuse_001';out.mkdir(exist_ok=False)
old=base/'wire_preconditioned_Xyce_001';build=old/'build'
source=old/'source/src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'
header=root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_warm_reuse_bounded.h'
flags=build/'src/CMakeFiles/XyceLib.dir/flags.make';link=build/'src/CMakeFiles/Xyce.dir/link.txt'
archive=build/'src/libxyce.a'
active=base/'wire_preconditioned_Xyce_002/install/bin/Xyce'
pins={str(p):digest(p) for p in (Path(__file__).resolve(),proof,source,header,flags,link,archive,active,
    build/'src/CMakeFiles/Xyce.dir/Xyce.C.o',base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002/owner.json')}
text=source.read_text()
assert text.count('OpenPLLWirePC::solve')==1
text=text.replace('OpenPLL_WirePreconditioner_v2.h',header.name).replace('OpenPLLWirePC::solve','OpenPLLWireBoundedReusePC::solve')
newsource=out/'N_LAS_AmesosSolver.C';newsource.write_text(text);shutil.copyfile(header,out/header.name)
newarchive=out/'libxyce.a';shutil.copyfile(archive,newarchive)
options={}
for line in flags.read_text().splitlines():
    if ' = ' in line:
        k,v=line.split(' = ',1);options[k]=shlex.split(v)
obj=out/'N_LAS_AmesosSolver.C.o';binary=out/'Xyce'
compile_command=['/usr/bin/g++',*options['CXX_DEFINES'],*options['CXX_INCLUDES'],*options['CXX_FLAGS'],'-c',str(newsource),'-o',str(obj)]
link_command=shlex.split(link.read_text())
for i,token in enumerate(link_command):
    if token=='libxyce.a':link_command[i]=str(newarchive)
    elif token=='CMakeFiles/Xyce.dir/Xyce.C.o':link_command[i]=str(build/'src'/token)
    elif token=='-o':assert link_command[i+1]=='Xyce';link_command[i+1]=str(binary)
for token in link_command:
    p=Path(token)
    if p.is_absolute() and p.is_file():pins[str(p)]=digest(p)
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
    deadline_uptime=deadline,experiment_deadline_restarted=False,native_circuit_started=False))
save(out/'input_manifest.json',dict(input_sha256=pins,original_source_and_archive_read_only=True))
child=None;receipts=[]
def limit():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
try:
    for label,command in [('compile',compile_command),('replace_archive_member',['/usr/bin/ar','r',str(newarchive),str(obj)]),('link',link_command)]:
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert remaining>0
        before=time.monotonic()
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                preexec_fn=limit,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            save(out/'status.json',dict(state=label,child_pid=child.pid,release_qualified=False))
            child.wait(timeout=remaining)
        receipts.append(dict(stage=label,command=command,exit_code=child.returncode,elapsed_s=time.monotonic()-before))
        save(out/'stage_receipts.json',receipts)
        assert child.returncode==0,label
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    save(out/'assessment.json',dict(experimental_build_completed=True,binary=str(binary),binary_sha256=digest(binary),
        input_sha256=pins,stages=receipts,live_binary_and_source_unchanged=True,
        native_controls_passed=False,release_qualified=False,adopted=False))
    save(out/'status.json',dict(state='built_requires_native_controls',release_qualified=False))
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False));raise
finally:stop()
