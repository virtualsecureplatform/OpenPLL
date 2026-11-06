"""Observe the original numerical control; retain its comparison without retries."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease


def run(base,target,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30})
    checker=Path(__file__).with_name('check_selected_dco_numerical_control_v2.py');owner=json.loads((target/'owner.json').read_text())
    files=[Path(__file__).resolve(),checker,base/'manifest.json',target/'owner.json'];pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,base=str(base),target=str(target),original_owner=owner,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        while True:
            state=json.loads((target/'status.json').read_text())['state']
            if state=='real_driver_DCO_diagnostic_complete':break
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original numerical control stopped before normal completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; original native untouched')
            save(output/'status.json',dict(state='waiting_for_original_numerical_control',release_ready=False));time.sleep(10)
        verify(pins);report=output/'comparison.json'
        with lease(1,1,deadline):
            with (output/'comparison.log').open('x') as log:subprocess.run(['/usr/bin/python3',str(checker),'--base',str(base),'--target',str(target),'--output',str(report)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},native_restarted=False,full_native_model_convergence_qualified=False,release_ready=False));save(output/'status.json',dict(state='numerical_control_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','target','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','target','output']))
