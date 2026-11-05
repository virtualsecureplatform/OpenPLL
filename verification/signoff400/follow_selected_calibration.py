"""Observe one bounded native calibration, then extract and assess it once."""
import argparse,json,subprocess,time,os
from pathlib import Path
from resources import identity,lease
from common_v3 import ROOT,sha,save,verify


def run(native,output):
    output.mkdir(parents=True,exist_ok=False)
    owner=json.loads((native/'owner.json').read_text());status=json.loads((native/'status.json').read_text())
    deadline=status.get('native_deadline_uptime',time.clock_gettime(time.CLOCK_BOOTTIME))+1800
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_native_completion',native=str(native),release_ready=False))
    while status['state']=='running_loaded_startup_260ns':
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native owner exited without terminal status; inspect original job')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('calibration observation deadline exhausted')
        time.sleep(10);status=json.loads((native/'status.json').read_text())
    if status['state']!='native_startup_completed_waveform_assessment_pending':raise RuntimeError(f'native job did not complete: {status}')
    manifest=json.loads((native/'manifest.json').read_text());verify(manifest['input_sha256'])
    source=ROOT/'tools/xyce_waveform/extract_selected.cpp';assessor=ROOT/'verification/signoff400/assess_selected_startup.py'
    pins={str(p):sha(p) for p in [source,assessor,native/'manifest.json']}
    os.sched_setaffinity(0,{24})
    with lease(1,2,deadline):
        save(output/'status.json',dict(state='extracting_completed_waveform',release_ready=False))
        subprocess.run(['g++','-O3','-std=c++17',source,'-o',output/'extract'],check=True,timeout=60)
        with (output/'extraction.log').open('w') as log:
            subprocess.run([output/'extract',native/'profile.raw',output/'signals.csv'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
        with (output/'assessment.log').open('w') as log:
            subprocess.run(['python3',assessor,'--output',output],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    verify(pins);verify(manifest['input_sha256'])
    save(output/'provenance.json',dict(input_sha256=pins,native_input_sha256=manifest['input_sha256'],raw_sha256=sha(native/'profile.raw'),artifacts={str(p):sha(p) for p in [output/'assessment.json',output/'signals.csv',output/'extraction.log']},diagnostic=True,release_ready=False))
    save(output/'status.json',dict(state='calibration_waveform_assessed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.native.resolve(),a.output.resolve())
