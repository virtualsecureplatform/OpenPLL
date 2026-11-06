"""Cache one actual saved native voltage state using an existing verified RAW identity.

This preserves a saved knot rather than interpolating capacitor states. It does
not qualify simulator restart semantics or a reduced boundary initialization.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_initial_snapshot import fingerprint


def run(native,snapshot,time_ns,output):
    if time_ns!=175:raise ValueError('only the planned pre-reset 175 ns checkpoint is supported')
    os.sched_setaffinity(0,{24});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='capturing_actual_saved_native_state',release_ready=False))
    try:
        sr=json.loads(snapshot.read_text());verify(sr['artifacts'])
        verify({p:d for p,d in sr['input_sha256'].items() if not p.endswith('/profile.raw')})
        raw=native/'profile.raw';manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        if sr['input_sha256'].get(str(manifest))!=sha(manifest) or str(raw) not in sr['input_sha256']:
            raise ValueError('verified original native identity required')
        before=fingerprint(raw)
        if before!=sr['source_file_fingerprint']:raise ValueError('RAW differs from verified snapshot source')
        source=ROOT/'tools/xyce_waveform/extract_saved_state_v2.cpp'
        paths=[snapshot,manifest,source,Path(__file__).resolve(),Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('common_v3.py')]
        pins={str(p):sha(p)for p in paths};binary=output/'extract';state=output/'saved_voltage_state.json'
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1,2,deadline):
            subprocess.run(['g++','-O3','-std=c++17',source,'-o',binary],check=True,timeout=120)
            pins[str(binary)]=sha(binary)
            execute([binary,raw,format(time_ns*1e-9,'.17g'),state],output/'extraction.log',deadline,2)
        data=json.loads(state.read_text())
        if len(data['variable_names'])!=sr['vectors'] or len(data['values'])!=sr['vectors'] or not 175e-9<=data['time_s']<=175.011e-9:
            raise ValueError('saved state vector or actual knot time differs')
        if fingerprint(raw)!=before:raise ValueError('native source RAW changed during extraction')
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(state):sha(state)},
            original_RAW_sha256=sr['input_sha256'][str(raw)],source_file_fingerprint=before,
            requested_time_ns=time_ns,actual_saved_time_s=data['time_s'],sample_index=data['sample_index'],vectors=sr['vectors'],
            actual_saved_knot_preserved_without_interpolation=True,
            initial_charge_or_restart_semantics_qualified=False,reduced_boundary_initialization_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='actual_saved_native_state_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('native','snapshot','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--time-ns',type=int,default=175);a=p.parse_args()
    run(a.native.resolve(),a.snapshot.resolve(),a.time_ns,a.output.resolve())
