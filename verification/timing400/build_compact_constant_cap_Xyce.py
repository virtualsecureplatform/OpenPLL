#!/usr/bin/env python3
"""Compile one capacitor object into a copied current archive, preserving live inputs."""
from datetime import datetime,timezone
import hashlib
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


def members(path):
    data=path.read_bytes();assert data[:8]==b'!<arch>\n';pos=8;raw=[];names=b''
    while pos<len(data):
        header=data[pos:pos+60];assert len(header)==60 and header[-2:]==b'`\n'
        name=header[:16].decode().strip();size=int(header[48:58]);pos+=60
        body=data[pos:pos+size];assert len(body)==size;pos+=size+(size%2)
        if name=='//':names=body
        raw.append((name,body))
    assert pos==len(data);result={}
    for name,body in raw:
        if name in ('/','//'):continue
        if name.startswith('/'):
            off=int(name[1:]);name=names[off:names.index(b'/\n',off)].decode()
        else:name=name.rstrip('/')
        assert name not in result;result[name]=hashlib.sha256(body).hexdigest()
    return result


def main():
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    candidate=base/'compact_constant_cap_source_001';source_proof=candidate/'assessment.json';prepared=json.loads(source_proof.read_text())
    for p,sha in {**prepared['input_sha256'],**prepared['candidate_sha256']}.items():assert digest(Path(p))==sha,p
    current=base/'wire_preconditioned_Xyce_bounded_reuse_001';proof=current/'recovered_build_assessment.json';built=json.loads(proof.read_text())
    archive=current/'libxyce.a';assert digest(archive)==built['input_sha256'][str(archive)]
    assert digest(Path(built['binary']))==built['binary_sha256']
    inherited=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json'
    deadline=min(time.clock_gettime(time.CLOCK_BOOTTIME)+600,json.loads(inherited.read_text())['deadline_uptime'])
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    out=base/'wire_preconditioned_Xyce_compact_caps_001';out.mkdir(exist_ok=False);sources=out/'source';sources.mkdir()
    for name in ['N_DEV_Capacitor.C','N_DEV_Capacitor.h']:shutil.copyfile(candidate/name,sources/name)
    oldbuild=base/'wire_preconditioned_Xyce_001/build';flags=oldbuild/'src/CMakeFiles/XyceLib.dir/flags.make';link=oldbuild/'src/CMakeFiles/Xyce.dir/link.txt'
    newarchive=out/'libxyce.a';shutil.copyfile(archive,newarchive);obj=out/'N_DEV_Capacitor.C.o';binary=out/'Xyce'
    options={}
    for line in flags.read_text().splitlines():
        if ' = ' in line:
            k,v=line.split(' = ',1);options[k]=shlex.split(v)
    compile_command=['/usr/bin/g++','-I'+str(sources),*options['CXX_DEFINES'],*options['CXX_INCLUDES'],*options['CXX_FLAGS'],'-c',str(sources/'N_DEV_Capacitor.C'),'-o',str(obj)]
    link_command=shlex.split(link.read_text())
    for i,token in enumerate(link_command):
        if token=='libxyce.a':link_command[i]=str(newarchive)
        elif token=='CMakeFiles/Xyce.dir/Xyce.C.o':link_command[i]=str(oldbuild/'src'/token)
        elif token=='-o':assert link_command[i+1]=='Xyce';link_command[i+1]=str(binary)
    inputs=[Path(__file__).resolve(),source_proof,proof,archive,Path(built['binary']),flags,link,inherited,
        sources/'N_DEV_Capacitor.C',sources/'N_DEV_Capacitor.h',root/'build/apptainer/openpll-release-modern.sif']
    for token in link_command:
        p=Path(token)
        if p.is_absolute() and p.is_file() and not p.is_relative_to(out):inputs.append(p)
    pins={str(p):digest(p) for p in inputs}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        native_circuit_started=False,budget_restarted=False,build_address_space_limit_GiB=8))
    save(out/'input_manifest.json',dict(input_sha256=pins,live_archive_and_binary_read_only=True))
    child=None;receipts=[]
    def limit():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    def stop():
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    try:
        for label,command in [('compile',compile_command),('replace_archive_member',['/usr/bin/ar','r',str(newarchive),str(obj)]),('link',link_command)]:
            remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert remaining>0;before=time.monotonic()
            with (out/(label+'.log')).open('x') as log:
                child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit,
                    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
                save(out/'status.json',dict(state=label,child_pid=child.pid,release_qualified=False));child.wait(timeout=remaining)
            receipts.append(dict(stage=label,command=command,exit_code=child.returncode,elapsed_s=time.monotonic()-before))
            save(out/'stage_receipts.json',receipts);assert child.returncode==0,label
        original,changed=members(archive),members(newarchive);assert original.keys()==changed.keys()
        differences=[name for name in original if original[name]!=changed[name]]
        assert differences==['N_DEV_Capacitor.C.o'] and changed[differences[0]]==digest(obj)
        for p,sha in pins.items():assert digest(Path(p))==sha,p
        assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
        save(out/'assessment.json',dict(experimental_build_completed=True,binary=str(binary),binary_sha256=digest(binary),
            input_sha256=pins,changed_archive_members=differences,unchanged_archive_members=len(original)-1,
            current_solver_object_preserved=True,live_archive_and_binary_unchanged=True,
            native_controls_passed=False,performance_gain_demonstrated=False,release_qualified=False,adopted=False))
        save(out/'status.json',dict(state='built_requires_native_controls',release_qualified=False))
    except Exception as error:
        stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False));raise
    finally:stop()


if __name__=='__main__':main()
