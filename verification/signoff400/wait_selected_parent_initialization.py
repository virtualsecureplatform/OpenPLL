"""Wait for live parent status publication before starting an existing observer."""
import argparse,json,subprocess,time
from pathlib import Path
from common_v3 import save,sha
from resources import identity


def run(parents,receipt,command):
    if receipt.exists():raise FileExistsError(receipt)
    receipt.mkdir();owners={str(p):json.loads((p/'owner.json').read_text())for p in parents}
    save(receipt/'owner.json',dict(pid=__import__('os').getpid(),birth=identity(__import__('os').getpid())))
    save(receipt/'inputs.json',dict(parents=owners,command=command,input_sha256={str(Path(__file__).resolve()):sha(__file__)},native_jobs_launched_by_wrapper=0,automatic_retry=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12*86400
    try:
        for parent in parents:
            while not (parent/'status.json').exists():
                owner=owners[str(parent)]
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('parent exited before initial status publication')
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('parent initialization observation expired')
                save(receipt/'status.json',dict(state='waiting_for_live_parent_initial_status',parent=str(parent),release_ready=False));time.sleep(10)
            if json.loads((parent/'status.json').read_text()).get('state')=='stopped_without_qualification':raise RuntimeError('parent stopped before observer launch')
        save(receipt/'status.json',dict(state='observer_running',release_ready=False))
        with (receipt/'observer.log').open('x')as log:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(receipt/'child.json',dict(pid=child.pid,birth=identity(child.pid),command=command))
            code=child.wait()
        if code:raise RuntimeError('observer stopped; no automatic retry')
        save(receipt/'status.json',dict(state='observer_completed',release_ready=False))
    except BaseException as e:
        save(receipt/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,action='append',required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    command=a.command[1:]if a.command[:1]==['--']else a.command
    if not command:p.error('observer command required')
    run([v.resolve()for v in a.parent],a.receipt.resolve(),command)
