#!/usr/bin/env python3
"""Build an isolated experimental adapter; preserve every installed stock build."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest, save

root=Path(__file__).resolve().parents[2]
base=root/'build/timing400/release_001'
out=base/'wire_preconditioned_Xyce_001'; out.mkdir(exist_ok=False)
start=time.monotonic(); deadline=start+1800
proof=base/'native_solver_probe_checks_001/assessment.json'
assert json.loads(proof.read_text())['native_SDK_probe_passed']
original=Path('/opt/Xyce')
header=root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner.h'
stock=base/'stock_serial_Xyce_001'
sdk=stock/'trilinos-install'
pins={str(p.resolve()):digest(p) for p in [Path(__file__),proof,header,
    original/'src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C',
    original/'CMakeLists.txt',stock/'xyce-install/bin/Xyce',Path('/opt/xyce/bin/Xyce'),
    root/'build/apptainer/openpll-release-modern.sif',sdk/'lib/cmake/Trilinos/TrilinosConfig.cmake']}
for path in (sdk/'lib').glob('*.a'): pins[str(path.resolve())]=digest(path)
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
    build_wall_limit_s=1800,maximum_build_workers=4,installed_builds_untouched=True))
def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),release_qualified=False,adopted=False,**extra))
status('copying_isolated_source')
source=out/'source'; shutil.copytree(original,source,ignore=shutil.ignore_patterns('.git'))
source_pins={str(path.relative_to(source)):digest(path) for path in source.rglob('*') if path.is_file()}
modified=source/'src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'
s=modified.read_text()
needle='#include <N_LAS_AmesosSolver.h>'
assert s.count(needle)==1
s=s.replace(needle,needle+'\n#include "OpenPLL_WirePreconditioner.h"')
needle='  timer_->resetStartTime();'
assert s.count(needle)==1
s=s.replace(needle,needle+'''\n
  // Opt-in experimental preconditioner. Original Newton equations are retained.
  if (std::getenv("OPENPLL_WIRE_PC")) {
    int result = OpenPLLWirePC::solve(*problem_, transpose);
    solutionTime_ = timer_->elapsedTime();
    return result;
  }
''')
modified.write_text(s)
shutil.copyfile(header,modified.parent/header.name)
changes=[]
for name,sha in source_pins.items():
    if digest(source/name)!=sha: changes.append(name)
assert changes==['src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C']
save(out/'source_manifest.json',dict(original_source_sha256=source_pins,
    modified_existing_files=changes,added_header_sha256=digest(modified.parent/header.name),
    modified_adapter_sha256=digest(modified),opt_in_environment_variable='OPENPLL_WIRE_PC'))
build=out/'build'; install=out/'install'
command=['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
    '-DCMAKE_C_COMPILER=/usr/bin/gcc','-DCMAKE_CXX_COMPILER=/usr/bin/g++',
    '-DCMAKE_INSTALL_PREFIX='+str(install),'-DTrilinos_ROOT='+str(sdk),
    '-DTrilinos_DIR='+str(sdk/'lib/cmake/Trilinos'),'-DXyce_PARALLEL_MPI=OFF',
    '-DXyce_STOKHOS_ENABLE=OFF','-DXyce_ROL=OFF','-DXyce_AMESOS2=OFF',
    '-DXyce_SHYLU=OFF','-DXyce_RELEASE=ON']
stages=[('configure',command),('build',['cmake','--build',str(build),'--parallel','4']),
        ('install',['cmake','--install',str(build)]),('version',[str(install/'bin/Xyce'),'-v'])]
save(out/'input_manifest.json',dict(input_sha256=pins,commands=stages,
    stock_SDK_reused=True,existing_source_or_build_changed=False,
    completed_qualification_campaign_extended=False,source_modified_only_in_isolated_copy=True))
receipts=[]; success=True
for stage,command in stages:
    remaining=deadline-time.monotonic()
    if remaining<=0: status('build_timeout_inconclusive'); success=False; break
    before=time.monotonic()
    with (out/(stage+'.log')).open('x') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
        status('experimental_build_running',stage=stage,child_pid=child.pid)
        timed_out=False
        try: code=child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out=True; os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL); child.wait()
            code=child.returncode
    receipts.append(dict(stage=stage,exit_code=code,timed_out=timed_out,elapsed_s=time.monotonic()-before))
    save(out/'stage_receipts.json',receipts)
    if code:
        status('build_timeout_inconclusive' if timed_out else 'experimental_build_nonpass',stage=stage,exit_code=code)
        success=False; break
assert all(digest(Path(p))==sha for p,sha in pins.items())
binary=install/'bin/Xyce'
save(out/'assessment.json',dict(experimental_build_completed=success,stages=receipts,
    binary=str(binary) if success else None,binary_sha256=digest(binary) if success else None,
    input_sha256=pins,stock_binaries_unchanged=True,stock_source_unchanged=True,
    simulator_equivalence_qualified=False,full_transient_tested=False,
    runtime_model_eligible=False,release_qualified=False,adopted=False))
if success: status('experimental_build_completed_not_qualified')
