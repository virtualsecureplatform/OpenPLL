"""Wait for one original DCO code control and compare its matching full reference."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def run(native,reference,provenance,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    owner=json.loads((native/'owner.json').read_text());checker=Path(__file__).with_name('compare_selected_dco_startup_aligned_v2.py')
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),checker,reference/'assessment.json',reference/'signals.csv',provenance,native/'owner.json']};verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_native=str(native),original_owner=owner,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            state=json.loads((native/'status.json').read_text())['state']
            if state=='real_driver_DCO_diagnostic_complete':break
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native code control stopped without normal completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native job unchanged')
            save(output/'status.json',dict(state='waiting_for_original_code_holdout',release_ready=False));time.sleep(10)
        verify(pins)
        command=['/usr/bin/python3',checker,'--native',native,'--reference',reference/'signals.csv','--reference-assessment',reference/'assessment.json','--reference-provenance',provenance,'--output',output/'comparison']
        with lease(1,2,deadline):
            with (output/'comparison.log').open('x') as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
        verify(pins);report=output/'comparison/assessment.json';r=json.loads(report.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},coarse=r['coarse'],fine=r['fine'],
            frequency_comparisons=r['frequency_comparisons'],native_restarted=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='DCO_code_holdout_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['native','reference','provenance','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['native','reference','provenance','output']))
