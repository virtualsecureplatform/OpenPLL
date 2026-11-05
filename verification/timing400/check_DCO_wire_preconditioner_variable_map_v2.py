#!/usr/bin/env python3
"""After native controls pass, verify full-DCO variable IDs without a transient."""
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

parser=argparse.ArgumentParser()
parser.add_argument('--controls-pid',type=int,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
args.output=args.output.resolve();args.output.mkdir(exist_ok=False)
controls=base/'wire_preconditioned_native_controls_004';proof=controls/'assessment.json'
identity=process(args.controls_pid)
assert identity['live'] and Path(identity['argv'][1]).name=='check_wire_preconditioned_native_controls_v4.py'
assert json.loads((controls/'owner.json').read_text())['runner_pid']==args.controls_pid
save(args.output/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
    controls_runner_identity=identity,maximum_controls_wait_s=2500,names_stage_wall_limit_s=600,
    native_address_space_limit_GiB=48,full_transient_attempted=False,
    completed_qualification_campaign_extended=False))
def status(state,**extra):
    save(args.output/'status.json',dict(state=state,runner_pid=os.getpid(),release_qualified=False,adopted=False,**extra))
status('waiting_for_identified_native_controls')
end=time.monotonic()+2500
while not proof.exists() and time.monotonic()<end:
    observed=process(args.controls_pid)
    if not observed['live'] or observed['argv']!=identity['argv']:break
    time.sleep(1)
if not proof.exists():status('controls_unavailable_no_DCO_started');raise SystemExit(0)
control=json.loads(proof.read_text());assert control['native_adapter_controls_passed']
build=base/'wire_preconditioned_Xyce_002/assessment.json';built=json.loads(build.read_text())
assert built['experimental_build_completed'];binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
metadata=base/'native_wire_preconditioner_metadata_001/assessment.json';model=json.loads(metadata.read_text())
assert model['native_GID_metadata_exported'] and digest(Path(model['metadata_file']))==model['metadata_sha256']
old=base/'DCO_native_linear_system_capture_002/native_variable_names.json'
assert digest(old)==model['source_variable_names_sha256']
source=base/'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002/point.cir'
deck=args.output/'point.cir';deck.write_bytes(source.read_bytes());assert digest(deck)==digest(source)
names=args.output/'candidate.names'
inputs=[Path(__file__),proof,build,binary,metadata,old,source,deck,Path(model['metadata_file']),
    root/'build/apptainer/openpll-release-modern.sif']
inputs+=model_files(deck,time.clock_gettime(time.CLOCK_BOOTTIME)+600)
pins={str(p.resolve()):digest(p) for p in inputs}
save(args.output/'input_manifest.json',dict(input_sha256=pins,circuit_byte_identical=True,
    native_command_purpose='names_export_only_no_transient'))
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(600,601))
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('OPENPLL_WIRE_PC',None)
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);assert not live_engines()
    before=time.monotonic();timed_out=False
    with (args.output/'native.log').open('x') as log:
        child=subprocess.Popen([str(binary),'-quiet','-namesfile',str(names),str(deck)],
            cwd=args.output,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True,preexec_fn=limits)
        status('native_DCO_names_export_running',native_pid=child.pid)
        try:code=child.wait(timeout=600)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            code=child.returncode
matched=False;metrics=None
if code==0 and names.exists():
    lines=names.read_text().splitlines();assert lines[0]=='HEADER'
    mapping={int(line.split()[0]):line.split()[1] for line in lines[1:]}
    reference=json.loads(old.read_text());assert len(mapping)==len(reference)
    assert set(mapping)==set(range(len(reference)))
    actual=[mapping[i] for i in range(len(reference))]
    matched=[name.upper() for name in actual]==[name.upper() for name in reference]
    metrics=dict(variables=len(actual),native_GIDs_match_reference=matched,
        candidate_names_sha256=digest(names),reference_names_sha256=digest(old))
assert all(digest(Path(p))==sha for p,sha in pins.items())
save(args.output/'assessment.json',dict(full_DCO_variable_map_verified=matched,native_exit=code,
    timed_out=timed_out,elapsed_s=time.monotonic()-before,metrics=metrics,input_sha256=pins,
    full_transient_attempted=False,original_circuit_unchanged=True,
    full_DCO_speedup_demonstrated=False,release_qualified=False,adopted=False))
status('completed_DCO_variable_map_check' if matched else ('timeout_inconclusive' if timed_out else 'native_variable_map_nonpass'))
