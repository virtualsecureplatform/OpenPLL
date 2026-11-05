"""Wait for the exact settling campaign, then reconcile all four controls once."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common import save,sha
from resources import identity,lease


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();campaign=root/'build/signoff400/startup_timing_mux2_4_settling_control_001';owner=json.loads((campaign/'owner.json').read_text());review=root/'verification/signoff400/review_mux2_4_numerical_controls_v2.py';target=root/'build/signoff400/startup_timing_mux2_4_numerical_review_002'
    paths=[campaign/'owner.json',campaign/'plan.json',review,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};deadline=owner['deadline_uptime']
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_exact_settling_producer')
    try:
        while not (campaign/'assessment.json').exists():
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('settling campaign deadline exhausted')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('settling producer stopped without assessment')
            time.sleep(2)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('review or producer plan changed')
        receipt=campaign/'assessment.json';a=json.loads(receipt.read_text());pins[str(receipt)]=sha(receipt)
        if not a['all_15_independent_settling_controls_terminal']:raise ValueError('terminal settling grid required')
        status('independently_reconciling_four_numerical_controls')
        with lease(1,1,deadline):
            with (out/'review.log').open('x') as log:subprocess.run(['python3',str(review),'--output',str(target)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        if any(sha(p)!=h for p,h in pins.items()):raise ValueError('review inputs changed')
        result=target/'assessment.json';save(out/'assessment.json',dict(input_sha256=pins,review=str(result),review_sha256=sha(result),four_control_review_complete=True,physical_timing_qualified=False,release_qualified=False));status('four_control_numerical_review_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
