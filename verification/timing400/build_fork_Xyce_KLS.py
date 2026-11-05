#!/usr/bin/env python3
"""Build pinned user-selected Xyce/KLS sources without changing golden tools."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tarfile
import time
from compile_local_C_operators_v2 import digest, save

root=Path(__file__).resolve().parents[2]
base=root/'build/timing400/release_001'
campaign=base/'fork_Xyce_KLS_001'; owner_path=campaign/'owner.json'
owner=json.loads(owner_path.read_text()); deadline=owner['deadline_uptime']
scratch=Path(owner['scratch']); xyce=scratch/'Xyce'; kls=scratch/'KLS'
out=campaign/'build_001';out.mkdir(exist_ok=False)
build=scratch/'build';install=scratch/'install'
sdk=base/'stock_serial_Xyce_001/trilinos-install'
child=None;receipts=[]

def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),
         observed_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
         release_qualified=False,adopted=False,**extra))

def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL);child.wait()

def limits():
    resource.setrlimit(resource.RLIMIT_AS,(32*1024**3,32*1024**3))

def git(path,*args):
    return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()

save(out/'owner.json',dict(runner_pid=os.getpid(),campaign_owner=str(owner_path),
     inherited_deadline_uptime=deadline,build_workers=8,budget_restarted=False,
     installed_golden_binary_modified=False,source_code_modified=False))
try:
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    sources=[xyce,kls]+[kls/'third_party'/name for name in ['metis','gklib','scotch','spral']]
    revisions={}
    for path in sources:
        assert not git(path,'status','--porcelain'),str(path)+' dirty'
        revisions[str(path)]=git(path,'rev-parse','HEAD')
    assert revisions[str(xyce)]==owner['source_commits']['Xyce']
    assert revisions[str(kls)]==owner['source_commits']['KLS']
    inputs={str(p):digest(p) for p in [Path(__file__).resolve(),owner_path,
        root/'build/apptainer/openpll-release-modern.sif',sdk/'lib/cmake/Trilinos/TrilinosConfig.cmake',
        Path('/opt/xyce/bin/Xyce')]}
    source_hashes={}
    for source in sources:
        for relative in git(source,'ls-files').splitlines():
            p=source/relative
            if p.is_file():source_hashes[str(p)]=digest(p)
    save(out/'source_manifest.json',dict(revisions=revisions,source_sha256=source_hashes,
         repositories_clean_before_build=True))
    snapshot=out/'source_snapshot.tar.gz'
    with tarfile.open(snapshot,'w:gz') as archive:
        for source in (xyce,kls):
            archive.add(source,arcname=source.name,
                filter=lambda info: None if '.git' in Path(info.name).parts else info)
    inputs[str(out/'source_manifest.json')]=digest(out/'source_manifest.json')
    inputs[str(snapshot)]=digest(snapshot)
    configure=['cmake','-S',str(xyce),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_COMPILER=/usr/bin/gcc','-DCMAKE_CXX_COMPILER=/usr/bin/g++',
        '-DCMAKE_Fortran_COMPILER=/usr/bin/gfortran','-DCMAKE_INSTALL_PREFIX='+str(install),
        '-DTrilinos_ROOT='+str(sdk),'-DTrilinos_DIR='+str(sdk/'lib/cmake/Trilinos'),
        '-DXyce_PARALLEL_MPI=OFF','-DXyce_STOKHOS_ENABLE=OFF','-DXyce_ROL=OFF',
        '-DXyce_AMESOS2=OFF','-DXyce_SHYLU=OFF','-DXyce_RELEASE=ON',
        '-DBUILD_TESTING=ON','-DXyce_KLS=ON','-DXyce_KLS_ROOT='+str(kls)]
    commands=[('configure',configure),
        ('build',['cmake','--build',str(build),'--parallel','8','--target','Xyce','testKLSAdapter']),
        ('adapter_test',['ctest','--test-dir',str(build),'-R','^testKLSAdapter$','--output-on-failure']),
        ('version',[str(build/'src/Xyce'),'-v'])]
    save(out/'input_manifest.json',dict(input_sha256=inputs,commands=commands))
    for label,command in commands:
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=300: raise TimeoutError('reserve five minutes for assessment before campaign deadline')
        started=time.monotonic()
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                preexec_fn=limits,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            status(label,child_pid=child.pid)
            try: code=child.wait(timeout=remaining-300)
            except subprocess.TimeoutExpired: raise TimeoutError(label+' campaign deadline')
        receipts.append(dict(stage=label,command=command,exit_code=code,elapsed_s=time.monotonic()-started))
        save(out/'stage_receipts.json',receipts)
        assert code==0,label+' failed; see retained log'
    assert '100% tests passed' in (out/'adapter_test.log').read_text()
    assert 'No tests were found' not in (out/'adapter_test.log').read_text()
    cache=(build/'CMakeCache.txt').read_text();assert 'Xyce_KLS:BOOL=ON' in cache
    binary=out/'bin/Xyce';binary.parent.mkdir();shutil.copy2(build/'src/Xyce',binary)
    shutil.copy2(build/'CMakeCache.txt',out/'CMakeCache.txt')
    for path,sha in source_hashes.items(): assert digest(Path(path))==sha,path
    for path,sha in inputs.items(): assert digest(Path(path))==sha,path
    save(out/'assessment.json',dict(fork_Xyce_KLS_build_passed=True,binary=str(binary),
         binary_sha256=digest(binary),source_revisions=revisions,input_sha256=inputs,
         adapter_regression_passed=True,source_code_modified=False,
         source_snapshot_sha256=digest(snapshot),full_DCO_equations_tested=False,
         native_waveform_controls_passed=False,selected_for_release_qualification=False,
         release_qualified=False,adopted=False))
    status('built_adapter_regression_passed_controls_pending',binary=str(binary))
except Exception as error:
    stop();save(out/'failure_receipt.json',dict(error_type=type(error).__name__,message=str(error),
         release_qualified=False,source_code_modified=False))
    status('timeout_inconclusive' if isinstance(error,TimeoutError) else 'build_nonpass')
    raise
finally:
    stop()
