#!/usr/bin/env python3
"""Resume the interrupted isolated build with a probe-validated include fix."""
from datetime import datetime,timezone,timedelta
import difflib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process

root=Path(__file__).resolve().parents[2]; base=root/'build/timing400/release_001'
prior=base/'wire_preconditioned_Xyce_001'
old_owner=json.loads((prior/'owner.json').read_text())
assert not process(old_owner['runner_pid'])['live']
old=json.loads((prior/'assessment.json').read_text())
assert not old['experimental_build_completed']
assert json.loads((prior/'stopped_for_adapter_include_fix.json').read_text())['worker_pid']>0
proof=base/'native_adapter_probe_checks_002/assessment.json'
assert json.loads(proof.read_text())['native_adapter_probe_passed']
# Conservatively inherit the first build's wall-clock deadline; do not reset it.
remaining=(datetime.fromisoformat(old_owner['started_utc'])+timedelta(seconds=1740)-datetime.now(timezone.utc)).total_seconds()
assert remaining>0
finish=time.monotonic()+remaining
out=base/'wire_preconditioned_Xyce_002';out.mkdir(exist_ok=False)
header=root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_v2.h'
source=prior/'source'; build=prior/'build'; install=out/'install'
modified=source/'src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'
original_manifest=json.loads((prior/'source_manifest.json').read_text())
assert digest(modified)==original_manifest['modified_adapter_sha256']
stock=base/'stock_serial_Xyce_001'
inputs=[Path(__file__),proof,header,prior/'owner.json',prior/'assessment.json',prior/'source_manifest.json',
    prior/'stopped_for_adapter_include_fix.json',build/'CMakeCache.txt',stock/'xyce-install/bin/Xyce',
    Path('/opt/xyce/bin/Xyce'),root/'build/apptainer/openpll-release-modern.sif']
inputs.extend((stock/'trilinos-install/lib').glob('*.a'))
pins={str(p.resolve()):digest(p) for p in inputs}
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
    inherited_original_owner=str(prior/'owner.json'),remaining_wall_limit_s=remaining,
    original_build_budget_restarted=False,original_qualification_campaign_extended=False,build_workers=4))
save(out/'input_manifest.json',dict(input_sha256=pins,prior_partial_objects_reused=True,
    changes_confined_to_isolated_worktree=True,original_build_budget_restarted=False))
old_text=modified.read_text();shutil.copyfile(modified,out/'prior_adapter.C')
old_header=modified.parent/'OpenPLL_WirePreconditioner.h';shutil.copyfile(old_header,out/'prior_header.h')
assert old_text.count('"OpenPLL_WirePreconditioner.h"')==1
text=old_text.replace('"OpenPLL_WirePreconditioner.h"','"OpenPLL_WirePreconditioner_v2.h"')
modified.write_text(text);shutil.copyfile(header,modified.parent/header.name)
(out/'adapter_include_fix.patch').write_text(''.join(difflib.unified_diff(old_text.splitlines(True),text.splitlines(True),
    fromfile='prior/N_LAS_AmesosSolver.C',tofile='resumed/N_LAS_AmesosSolver.C')))
save(out/'source_manifest.json',dict(shared_isolated_worktree=str(source),
    prior_adapter_sha256=digest(out/'prior_adapter.C'),prior_header_sha256=digest(out/'prior_header.h'),
    modified_adapter_sha256=digest(modified),new_header_sha256=digest(modified.parent/header.name),
    original_source_tree_preserved_in_SIF=True,stock_builds_untouched=True))
save(prior/'superseded_by_build_002.json',dict(successor=str(out),
    prior_adapter_backup=str(out/'prior_adapter.C'),prior_header_backup=str(out/'prior_header.h'),
    reason='Reuse unqualified partial objects after independently verified missing-include repair',
    original_assessment_and_receipts_preserved=True))
def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),release_qualified=False,adopted=False,**extra))
receipts=[];success=True
stages=[('build',['cmake','--build',str(build),'--parallel','4']),
    ('install',['cmake','--install',str(build),'--prefix',str(install)]),('version',[str(install/'bin/Xyce'),'-v'])]
for stage,command in stages:
    left=finish-time.monotonic()
    if left<=0: status('build_timeout_inconclusive');success=False;break
    before=time.monotonic()
    with (out/(stage+'.log')).open('x') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
        status('experimental_build_running',stage=stage,child_pid=child.pid)
        timed_out=False
        try: code=child.wait(timeout=left)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            code=child.returncode
    receipts.append(dict(stage=stage,exit_code=code,timed_out=timed_out,elapsed_s=time.monotonic()-before))
    save(out/'stage_receipts.json',receipts)
    if code:
        status('build_timeout_inconclusive' if timed_out else 'experimental_build_nonpass',stage=stage,exit_code=code)
        success=False;break
assert all(digest(Path(p))==sha for p,sha in pins.items())
binary=install/'bin/Xyce'
save(out/'assessment.json',dict(experimental_build_completed=success,stages=receipts,
    binary=str(binary) if success else None,binary_sha256=digest(binary) if success else None,
    input_sha256=pins,stock_binaries_unchanged=True,stock_source_unchanged=True,
    resumed_after_header_probe_pass=True,original_build_budget_restarted=False,
    simulator_equivalence_qualified=False,full_transient_tested=False,
    runtime_model_eligible=False,release_qualified=False,adopted=False))
if success:status('experimental_build_completed_not_qualified')
