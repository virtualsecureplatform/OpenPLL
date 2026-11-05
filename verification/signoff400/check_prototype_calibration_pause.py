"""Exercise reference-pause calibration control on the exact synthesized RTL.

The oscillator is an ideal gated 400 MHz clock. This checks control protocol,
not analog frequency accuracy, capture or a final macro replay qualification.
"""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease

def run(candidate,output):
    receipt=candidate/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    definition=candidate/'sources.json';rtl=[candidate/n for n in json.loads(definition.read_text())['files']]
    if any(a['candidate_source_sha256'].get(str(p))!=sha(p) for p in rtl):raise ValueError('exact synthesized source bundle required')
    bench=ROOT/'verification/prototype400/tb_calibration_reference_pause.v';tools=[Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    pins={str(p):sha(p) for p in (receipt,definition,*rtl,bench,*tools,Path(__file__).resolve())}
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');binary=output/'calibration.vvp'
    with lease(1,2,deadline):
        execute([tools[0],'-g2012','-s','tb_calibration_reference_pause','-o',binary,*rtl,bench],output/'compile.log',deadline,2)
        execute([tools[1],binary],output/'run.log',deadline,2)
    text=(output/'run.log').read_text()
    if text.count('CALIBRATION_PAUSE_OK')!=2 or any(token not in text for token in ('CALIBRATION_RESUME_OK','CALIBRATION_RESET_REPROGRAM_OK')):raise ValueError('incomplete calibration protocol witness')
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,output/'compile.log',output/'run.log')},exact_synthesized_source_bundle_executed=True,reference_pause_preserves_seed_and_keeps_oscillator_enabled=True,loop_tracking_remains_disabled_during_pause=True,reference_resume_and_reset_reprogram_controls_pass=True,oscillator_model='ideal gated 400 MHz clock',analog_calibration_or_capture_qualified=False,final_handoff_replay_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
