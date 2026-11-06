"""Wait for both original code comparisons and assess their measured tuning increment."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from follow_selected_dco_clock_slope import run as compare


def run(base,target,first,second,inventory,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    owners=[json.loads((d/'owner.json').read_text()) for d in [first,second]]
    files=[Path(__file__).resolve(),Path(__file__).with_name('follow_selected_dco_clock_slope.py'),inventory]+[d/n for d in [first,second] for n in ['owner.json','inputs.json']]
    pins={str(f):sha(f) for f in files};save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_comparisons=[str(first),str(second)],original_owners=owners,automatic_native_launch=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        while True:
            pending=[]
            for d,owner in zip([first,second],owners):
                state=json.loads((d/'status.json').read_text())['state']
                if state=='DCO_code_holdout_compared':continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=str(owner['birth']):raise RuntimeError('original comparison stopped: '+str(d))
                pending.append(str(d))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native cases unchanged')
            save(output/'status.json',dict(state='waiting_for_both_original_code_comparisons',pending=pending,release_ready=False));time.sleep(10)
        verify(pins);compare(base,target,first/'comparison/assessment.json',second,inventory,output/'comparison')
        report=output/'comparison/assessment.json';r=json.loads(report.read_text());verify(r['input_sha256']);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},records=r['records'],constant_offset_correction_applied=False,tuning_curve_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='repaired_load_two_code_increment_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','target','first','second','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','target','first','second','inventory','output']))
