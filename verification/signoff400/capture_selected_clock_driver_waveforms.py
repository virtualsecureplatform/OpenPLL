"""Extract native clock-driver waveforms for independent edge-shape holdouts.

Preserve every saved knot; verify the full-RAW fingerprint against a prior
complete checksum receipt. Native source shape is evidence, not interface
qualification or permission to extrapolate its time coverage.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_initial_snapshot import fingerprint
from check_selected_boundary_waveforms import bind


def run(drivers,inventory,native,snapshot_receipt,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='extracting_native_clock_driver_shapes',release_ready=False))
    try:
        dv=json.loads(drivers.read_text());iv=json.loads(inventory.read_text());sr=json.loads(snapshot_receipt.read_text())
        verify(dv['input_sha256']);verify(iv['input_sha256']);verify(sr['artifacts'])
        shared={p:d for p,d in dv['input_sha256'].items() if p in iv['input_sha256']}
        if len(shared)<3 or any(iv['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('driver and native primitive inventories differ')
        manifest=native/'manifest.json';m=json.loads(manifest.read_text())
        if not any(p.endswith('/model.spice') and m['input_sha256'].get(p)==d for p,d in iv['input_sha256'].items()):raise ValueError('native reference physical model mismatch')
        raw=native/'profile.raw'
        if str(raw) not in sr['input_sha256'] or fingerprint(raw)!=sr['source_file_fingerprint']:raise ValueError('native RAW must match verified snapshot identity')
        if sr['input_sha256'].get(str(manifest))!=sha(manifest):raise ValueError('snapshot native manifest identity mismatch')
        names=[]
        with raw.open() as f:
            for line in f:
                if line.strip()=='Variables:':break
            for line in f:
                if line.strip()=='Values:':break
                index,name,_=line.split()
                if int(index)!=len(names):raise ValueError('invalid native variable order')
                names.append(name)
        roles=dv['clock_drivers'];nodes=[v['node'] for v in roles.values()];bound=bind(nodes,names)
        if not bound['all_bound']:raise ValueError('all physical clock drivers must have native saved voltages')
        source=ROOT/'tools/xyce_waveform/extract_boundary_pwl.cpp'
        pins={str(p):sha(p) for p in [drivers,inventory,manifest,snapshot_receipt,source,Path(__file__).resolve(),Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py')]}
        indices=output/'indices.txt';indices.write_text(''.join(str(bound['bindings'][node]['index'])+'\n' for node in nodes))
        extracted=output/'waveforms';extracted.mkdir();binary=output/'extract'
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1,2,deadline):
            subprocess.run(['g++','-O3','-std=c++17',str(source),'-o',str(binary)],check=True,timeout=120)
            pins.update({str(p):sha(p) for p in [indices,binary]})
            execute([binary,raw,indices,extracted],output/'extraction.log',deadline,2)
        if fingerprint(raw)!=sr['source_file_fingerprint']:raise ValueError('native RAW changed during extraction')
        verify(pins);pins[str(raw)]=sr['input_sha256'][str(raw)]
        files={str(p):sha(p) for p in extracted.glob('*.pwl')}
        if len(files)!=len(roles):raise ValueError('clock driver waveform export incomplete')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=files,
            clock_driver_waveforms={role:dict(node=roles[role]['node'],file=str(extracted/f'boundary_{i}.pwl')) for i,role in enumerate(roles)},
            exact_saved_knots_preserved=True,source_complete_and_all_values_finite=True,
            source_time_coverage_s=[0,260e-9],active_detector_characterized_by_this_trace=False,
            edge_shape_holdouts_completed=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_clock_driver_waveforms_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['drivers','inventory','native','snapshot-receipt','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{30});run(*(getattr(a,n.replace('-','_')).resolve() for n in ['drivers','inventory','native','snapshot-receipt','output']))
