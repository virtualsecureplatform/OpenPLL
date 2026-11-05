"""Replay real functional and native fixtures with checkout/home/host-tmp hidden.

This is a staging control, not the final macro package or release gate.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease

def run(candidate,capture,output):
    cr=candidate/'assessment.json';a=json.loads(cr.read_text());verify(a['artifacts'])
    sr=capture/'assessment.json';r=json.loads(sr.read_text());verify(r['artifacts'])
    definition=candidate/'sources.json';rtl=json.loads(definition.read_text())['files']
    if any(a['candidate_source_sha256'].get(str(candidate/p))!=sha(candidate/p) for p in rtl):raise ValueError('exact synthesized RTL bundle required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    bench=ROOT/'verification/prototype400/tb_calibration_reference_burst.v';worker=Path(__file__).with_name('prototype_isolated_smoke_worker.py')
    source_deck=capture/'refinement.cir';cell=capture/'cell.spice';init=capture/'.spiceinit';gold=capture/'waveform.dat'
    if r['artifacts'].get(str(gold))!=sha(gold):raise ValueError('native golden waveform is not pinned')
    paths=[cr,sr,definition,*[candidate/p for p in rtl],image,ng,bench,worker,source_deck,cell,init,gold,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};output.mkdir(parents=True,exist_ok=False)
    inputs=output/'inputs';work=output/'work';inputs.mkdir();work.mkdir()
    for p in rtl:
        target=inputs/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(candidate/p,target)
    for folder in ('tb','native','tools'):(inputs/folder).mkdir()
    shutil.copyfile(bench,inputs/'tb/calibration.v');shutil.copyfile(worker,inputs/'replay.py');shutil.copy2(ng,inputs/'tools/ngspice');shutil.copyfile(cell,inputs/'native/cell.spice');shutil.copyfile(init,inputs/'native/.spiceinit')
    text=source_deck.read_text();before='"'+str(cell)+'"'
    if text.count(before)!=1 or text.count(str(gold))!=1:raise ValueError('exact source include/output normalization required')
    text=text.replace(before,'"/inputs/native/cell.spice"').replace(str(gold),'/work/waveform.dat')
    if str(ROOT) in text or '/tmp/' in text:raise ValueError('checkout or host scratch dependency in normalized native deck')
    (inputs/'native/refinement.cir').write_text(text)
    files={str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()}
    manifest=inputs/'manifest.json';save(manifest,dict(files=files,rtl=rtl,native_waveform_sha256=sha(gold),staging_smoke_only=True,release_ready=False))
    sentinel_dir=Path(tempfile.mkdtemp(prefix='openpll-clean-smoke-sentinel-'));sentinel=sentinel_dir/'host-only';sentinel.write_text('host scratch visibility control\n')
    command=['apptainer','exec','--containall','--cleanenv','--no-home','--no-mount','home,cwd,hostfs,bindpaths','--bind',f'{inputs}:/inputs:ro,{work}:/work','--pwd','/work',image,'/usr/bin/python3','/inputs/replay.py','--inputs','/inputs','--work','/work','--forbidden',ROOT,'--forbidden',sentinel]
    save(output/'input_manifest.json',dict(input_sha256=pins,normalized_files=files,command=list(map(str,command)),retained_host_scratch_sentinel=str(sentinel),release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    with lease(1,4,deadline):execute(command,output/'replay.log',deadline,4)
    verify(pins);result=work/'assessment.json';q=json.loads(result.read_text())
    if q['source_manifest_sha256']!=sha(manifest) or not q['functional_replay_pass'] or not q['native_waveform_byte_identical'] or not q['host_checkout_and_scratch_hidden']:raise ValueError('isolated functional/native replay did not pass')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (manifest,result,output/'replay.log',work/'functional.log',work/'native.log',work/'waveform.dat')},actual_functional_and_native_replays_passed_in_isolation=True,only_explicit_readonly_inputs_and_private_work_bound=True,staging_smoke_only=True,final_selected_macro_or_package_replay_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','capture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.capture.resolve(),a.output.resolve())
