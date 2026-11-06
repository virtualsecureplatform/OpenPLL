"""Immutable selected-RTL/VPI build cache with source and runtime identity checks."""
import argparse,json,os,re,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease

def fingerprint(path):
    s=path.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

TOOLS=('/usr/bin/iverilog','/usr/bin/iverilog-vpi','/usr/bin/vvp','/usr/bin/ldd')

def build_inputs(detector):
    pins=source_pins()
    files=[detector,ROOT/'tb/tb_programmed400_closed_loop_phased.v',ROOT/'tb/Prototype400ClockTiming.v',
        ROOT/'tb/Prototype400ReferencePhase.v',ROOT/'verification/timing400/phase_clock_vpi.cpp',
        ROOT/'verification/timing400/phase_clock.h',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('runtime_common.py')]
    pins.update({str(p):sha(p)for p in files})
    pins.update({p:sha(p)for p in TOOLS})
    return pins

def libraries(binary):
    result=subprocess.run(['/usr/bin/ldd',str(binary)],check=True,capture_output=True,text=True,timeout=10)
    paths=set()
    for line in result.stdout.splitlines():
        found=re.search(r'(?:=>\s+|^\s*)(/[^\s]+)',line)
        if found:paths.add(str(Path(found[1]).resolve()))
        elif 'not found'in line:raise ValueError('runtime library missing')
    if not paths:raise ValueError('resolved runtime library closure required')
    return {p:sha(p)for p in paths}

def check_identity(record,expected,image_fingerprint):
    if record.get('state')!='selected_RTL_VPI_build_complete'or record.get('build_inputs')!=expected:
        raise ValueError('cache source, detector or toolchain identity differs')
    if record.get('image_fingerprint')!=image_fingerprint:raise ValueError('declared image changed since verified build')

def build(detector,image,output):
    output.mkdir(parents=True,exist_ok=False);pins=build_inputs(detector)
    before=fingerprint(image);digest=sha(image)
    if fingerprint(image)!=before:raise ValueError('image changed while hashing')
    rtl=[p for p in source_pins()if p.endswith('.v')and not p.endswith('IntegerPLL_400MHz_PrototypeTop.v')]
    commands=[['/usr/bin/iverilog-vpi',ROOT/'verification/timing400/phase_clock_vpi.cpp'],
        ['/usr/bin/iverilog','-g2012','-s','tb_programmed400_closed_loop','-o',output/'loop.vvp',*rtl,
         ROOT/'tb/tb_programmed400_closed_loop_phased.v',ROOT/'tb/Prototype400ClockTiming.v',ROOT/'tb/Prototype400ReferencePhase.v',detector]]
    for index,command in enumerate(commands):
        with (output/f'compile_{index}.log').open('x')as log:
            subprocess.run(list(map(str,command)),cwd=output,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    artifacts={str(output/n):sha(output/n)for n in ('loop.vvp','phase_clock_vpi.vpi')}
    runtime=libraries('/usr/bin/vvp');runtime.update(libraries(output/'phase_clock_vpi.vpi'))
    verify(pins);verify(artifacts)
    if fingerprint(image)!=before:raise ValueError('image changed during compilation')
    save(output/'assessment.json',dict(state='selected_RTL_VPI_build_complete',build_inputs=pins,
        input_sha256=dict(pins,**{str(image):digest}),artifacts=artifacts,runtime_library_sha256=runtime,
        image=str(image),image_fingerprint=before,commands=[list(map(str,c))for c in commands],
        compiler_environment={n:os.environ.get(n)for n in ('CC','CXX','CFLAGS','CXXFLAGS','LDFLAGS','CPATH','LIBRARY_PATH')},
        scope='Compiled selected digital RTL and diagnostic detector only; calibration and clock timing remain per-case inputs.',release_ready=False))

def load(cache,detector):
    receipt=cache/'assessment.json';record=json.loads(receipt.read_text());expected=build_inputs(detector)
    image=Path(record['image']);check_identity(record,expected,fingerprint(image))
    verify({p:d for p,d in record['input_sha256'].items()if p!=str(image)})
    artifacts=record['artifacts']
    if set(artifacts)!={str(cache/n)for n in ('loop.vvp','phase_clock_vpi.vpi')}:raise ValueError('cache artifacts must belong to this cache')
    verify(artifacts)
    runtime=libraries('/usr/bin/vvp');runtime.update(libraries(cache/'phase_clock_vpi.vpi'))
    if runtime!=record['runtime_library_sha256']:raise ValueError('actual resolved runtime libraries differ')
    # The large image was checksummed at creation. Its complete filesystem
    # fingerprint is rechecked; sources, tools, artifacts and actual libraries
    # are rehashed on every reuse. Cases pin this immutable checksum receipt.
    pins={p:d for p,d in record['input_sha256'].items()if p!=str(image)}
    pins.update(artifacts);pins.update(runtime);pins[str(receipt)]=sha(receipt)
    return pins

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('detector','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{16})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
        build(*(getattr(a,n).resolve()for n in ('detector','image','output')))
