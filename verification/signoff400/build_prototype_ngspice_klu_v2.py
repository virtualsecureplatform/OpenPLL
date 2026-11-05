"""Build unchanged upstream ngspice47 with its standard KLU backend in an isolated prefix."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import shutil
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def inside(config):
    c=json.loads(config.read_text());source=Path(c['source']);prefix=Path(c['prefix']);deadline=c['deadline_uptime']
    commands=[['./configure','--prefix='+str(prefix),'--with-x=no','--with-readline=no',
        '--enable-xspice','--disable-cider','--enable-klu','--disable-osdi'],['make','-j4'],['make','-j4','install']]
    for command in commands:
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('KLU build deadline')
        print('BUILD_STEP',json.dumps(command),flush=True)
        subprocess.run(command,cwd=source,check=True,timeout=remaining)
    config_h=source/'src/include/ngspice/config.h'
    if not any(line.startswith('#define KLU') for line in config_h.read_text().splitlines()):raise ValueError('KLU was not compiled')
    persistent_config=Path(c['output'])/'compiled_config.h';shutil.copyfile(config_h,persistent_config)
    binary=prefix/'bin/ngspice'
    version=subprocess.check_output([binary,'--version'],text=True,timeout=30)
    save(Path(c['output'])/'native_assessment.json',dict(commands=commands,
         compiler=subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],version=version,
         input_sha256={str(persistent_config):sha(persistent_config)},artifacts={str(binary):sha(binary)},
         stock_KLU_compiled=True,device_model_code_modified=False,validated_for_prototype=False,release_ready=False))


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=4,memory_GiB=8,automatic_identical_retry=False))
    archive=ROOT/'build/tools/ngspice47/ngspice_47+ds.orig.tar.gz';image=ROOT/'build/apptainer/openpll-release-modern.sif'
    expected='004b2f7af4c862ed56a89a353e87889b58c21a5a56d13f45a9138d681c3f5dad'
    if sha(archive)!=expected:raise ValueError('upstream source archive changed')
    paths=[archive,image,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    scratch=Path(tempfile.mkdtemp(prefix='openpll-ngspice47-klu-'))
    save(output/'status.json',dict(state='local_source_extraction_running',release_ready=False))
    with tarfile.open(archive) as source:source.extractall(scratch,filter='data')
    source=scratch/'tmpsndfibtf'
    config=output/'config.json';save(config,dict(source=str(source),prefix=str(output/'install'),output=str(output),deadline_uptime=deadline))
    save(output/'input_manifest.json',dict(input_sha256=pins,bootstrap_tool='/usr/bin/autoreconf',
         build_scratch_is_not_a_runtime_dependency=True,
         only_intended_build_option_change='enable stock KLU instead of disable KLU'))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    try:
        save(output/'status.json',dict(state='waiting_for_build_resource_lease',release_ready=False))
        with lease(4,8,deadline):
            save(output/'status.json',dict(state='host_libtool_bootstrap_running',release_ready=False))
            with (output/'bootstrap.log').open('x') as log:
                subprocess.run(['/usr/bin/autoreconf','-fi'],cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            with tarfile.open(output/'bootstrapped_source.tar.gz','w:gz') as packed:packed.add(source,arcname='source')
            save(output/'status.json',dict(state='stock_ngspice_KLU_build_running',release_ready=False))
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside',config],output/'build.log',deadline,8)
            verify(pins)
        receipt=output/'native_assessment.json'
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (receipt,output/'compiled_config.h',output/'bootstrapped_source.tar.gz')},
             stock_KLU_compiled=True,device_model_code_modified=False,native_regression_complete=False,
             validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='KLU_build_complete_native_regression_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    elif a.output:run(a.output.resolve())
    else:p.error('output required')
