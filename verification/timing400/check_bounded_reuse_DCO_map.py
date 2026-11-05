#!/usr/bin/env python3
"""Verify full-DCO IDs with the new binary after the old native is terminal."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines,model_files
from run_DCO_gear_fallback_v3 import admission_lock
parser=argparse.ArgumentParser();parser.add_argument('--admission-lock-fd',type=int,required=True);parser.add_argument('--handoff',type=Path,required=True)
args=parser.parse_args();root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
handoff=json.loads(args.handoff.read_text());deadline=handoff['deadline_uptime']
assert not process(handoff['source_native_pid'])['live'] and not process(handoff['source_runner_pid'])['live']
assert digest(Path(handoff['source_point'])/'assessment.json')==handoff['prior_assessment_sha256']
audit=base/'bounded_reuse_native_controls_audit_002/assessment.json'
assert json.loads(audit.read_text())['completed_native_control_audit_passed']
proof=base/'wire_preconditioned_Xyce_bounded_reuse_001/recovered_build_assessment.json';built=json.loads(proof.read_text());binary=Path(built['binary'])
assert built['experimental_build_completed'] and digest(binary)==built['binary_sha256']
metadata=base/'native_wire_preconditioner_metadata_001/assessment.json';model=json.loads(metadata.read_text())
reference=base/'DCO_native_linear_system_capture_002/native_variable_names.json'
assert digest(reference)==model['source_variable_names_sha256']
out=base/'DCO_bounded_reuse_variable_map_001';out.mkdir(exist_ok=False)
source=Path(handoff['source_point'])/'point.cir';deck=out/'point.cir';deck.write_bytes(source.read_bytes())
names=out/'candidate.names'
inputs=[Path(__file__).resolve(),args.handoff,audit,proof,binary,metadata,reference,source,deck,Path(model['metadata_file']),root/'build/apptainer/openpll-release-modern.sif']
inputs+=model_files(deck,deadline)
pins={str(p.resolve()):digest(p) for p in inputs}
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,full_transient_attempted=False))
save(out/'input_manifest.json',dict(input_sha256=pins,original_circuit_byte_identical=True))
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,601))
with admission_lock(base,args.admission_lock_fd) as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);active=live_engines();assert len(active)<4
    assert not any(any('DCO_domain_' in arg for arg in process(pid)['argv']) for pid in active)
    mem={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()};assert mem['MemAvailable']>=28*1024**3
    before=time.monotonic();timed_out=False
    with (out/'native.log').open('x') as log:
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('OPENPLL_WIRE_PC',None)
        command=[str(binary),'-quiet','-namesfile',str(names),str(deck)]
        child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True,preexec_fn=limits)
        save(out/'status.json',dict(state='native_names_export_running',native_pid=child.pid,release_qualified=False))
        save(out/'launch.json',dict(command=command,pid=child.pid,native_before=active,maximum_native_workers=4,deadline_uptime=deadline))
        try:code=child.wait(timeout=min(600,max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            code=child.returncode
matched=False;metrics=None
if code==0 and names.exists():
    lines=names.read_text().splitlines();assert lines[0]=='HEADER'
    mapping={int(line.split()[0]):line.split()[1].upper() for line in lines[1:]}
    expected=[name.upper() for name in json.loads(reference.read_text())]
    assert set(mapping)==set(range(len(expected)))
    matched=[mapping[i] for i in range(len(expected))]==expected
    metrics=dict(variables=len(expected),native_GIDs_match_reference=matched,candidate_names_sha256=digest(names))
for p,sha in pins.items():assert digest(Path(p))==sha,p
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
save(out/'assessment.json',dict(full_DCO_variable_map_verified=matched,native_exit=code,timed_out=timed_out,
    elapsed_s=time.monotonic()-before,metrics=metrics,input_sha256=pins,full_transient_attempted=False,release_qualified=False))
save(out/'status.json',dict(state='native_map_passed' if matched else 'native_map_inconclusive_or_nonpass',release_qualified=False))
assert matched
