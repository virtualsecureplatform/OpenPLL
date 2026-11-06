"""Re-extract an immutable reference CSV and bind it to its retained native RAW."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_initial_snapshot import fingerprint


def run(native,snapshot,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='reextracting_retained_native_reference',release_ready=False))
    try:
        receipt=snapshot/'assessment.json';sr=json.loads(receipt.read_text());verify(sr['artifacts'])
        raw=native/'profile.raw';manifest=native/'manifest.json';nm=json.loads(manifest.read_text())
        if json.loads((native/'status.json').read_text())['state']!='completed_startup_observed_not_tracking_at_260ns':raise ValueError('normally completed original reference required')
        if fingerprint(raw)!=sr['source_file_fingerprint'] or sr['input_sha256'].get(str(manifest))!=sha(manifest):raise ValueError('verified original RAW identity required')
        verify(nm['input_sha256'])
        original=native/'waveform_assessment';source=ROOT/'tools/xyce_waveform/extract_selected.cpp';assessor=ROOT/'verification/signoff400/assess_selected_startup.py'
        paths=[manifest,receipt,original/'assessment.json',original/'signals.csv',source,assessor,Path(__file__).resolve(),Path(__file__).with_name('capture_selected_native_initial_snapshot.py')]
        pins={str(p):sha(p) for p in paths};verify(pins);binary=output/'extract';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1,2,deadline):
            subprocess.run(['g++','-O3','-std=c++17',source,'-o',binary],check=True,timeout=120)
            pins[str(binary)]=sha(binary)
            execute([binary,raw,output/'signals.csv'],output/'extraction.log',deadline,2)
            if sha(output/'signals.csv')!=pins[str(original/'signals.csv')]:raise ValueError('original selected CSV not reproduced byte-for-byte')
            with (output/'assessment.log').open('x') as log:subprocess.run(['/usr/bin/python3',assessor,'--output',output],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        before=json.loads((original/'assessment.json').read_text());after=json.loads((output/'assessment.json').read_text())
        if before!=after:raise ValueError('original native assessment not reproduced')
        if fingerprint(raw)!=sr['source_file_fingerprint']:raise ValueError('original RAW changed during extraction')
        verify(pins);pins[str(raw)]=sr['input_sha256'][str(raw)]
        artifacts={str(p):sha(p) for p in [original/'signals.csv',original/'assessment.json',output/'signals.csv',output/'assessment.json',output/'extraction.log']}
        save(output/'provenance.json',dict(input_sha256=pins,native_input_sha256=nm['input_sha256'],raw_sha256=sr['input_sha256'][str(raw)],source_file_fingerprint=sr['source_file_fingerprint'],
            artifacts=artifacts,original_CSV_reproduced_byte_for_byte=True,original_assessment_reproduced=True,diagnostic=True,release_ready=False))
        save(output/'status.json',dict(state='retained_native_reference_provenance_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['native','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['native','snapshot','output']))
