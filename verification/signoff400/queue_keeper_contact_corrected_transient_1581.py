"""Observe one live DC prerequisite and run one changed-extraction native capture."""
import json,os,time
from runtime_common import ROOT,save
from resources import identity
from run_keeper_contact_corrected_transient import run

def main():
    base=ROOT/'build/signoff400';smoke=base/'selected_keeper_contact_corrected_DC_1580'
    output=base/'selected_keeper_contact_corrected_transient_queue_1582';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((smoke/'owner.json').read_text());deadline=time.monotonic()+86400
    try:
        while True:
            status=json.loads((smoke/'status.json').read_text())
            if status['state']=='flat_native_reset_DC_complete' and (smoke/'assessment.json').exists():break
            if status['state']=='stopped_without_qualification':raise RuntimeError('DC prerequisite stopped')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('DC owner disappeared without completion')
            if time.monotonic()>=deadline:raise TimeoutError('DC observation deadline')
            save(output/'status.json',dict(state='waiting_for_live_DC_completion',release_ready=False));time.sleep(10)
        save(output/'status.json',dict(state='running_one_corrected_transient',release_ready=False))
        run(smoke,base/'selected_keeper_contact_corrected_fine134_1581',134,27,23,10)
        save(output/'status.json',dict(state='corrected_transient_assessed',release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':main()
