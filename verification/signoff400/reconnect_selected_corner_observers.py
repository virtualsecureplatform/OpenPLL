"""Reconnect unchanged corner observers after recovered parent initialization."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def parent_ready(parent,watchdog):
    status=parent/'status.json';owner=parent/'owner.json'
    if status.exists() and owner.exists():
        s=json.loads(status.read_text());o=json.loads(owner.read_text())
        if s.get('state')=='stopped_without_qualification':raise RuntimeError('parent stopped: '+str(parent))
        if identity(o['pid'])!=o['birth'] and not(parent/'assessment.json').exists():raise RuntimeError('parent exited without assessment')
        return True
    o=json.loads((watchdog/'owner.json').read_text())
    if identity(o['pid'])!=o['birth']:raise RuntimeError('initialization watchdog exited before parent publication')
    return False


def run(ff,remaining,watchdog,prior,tt_frame,output):
    if output.exists():raise FileExistsError(output)
    protocol=json.loads((prior/'protocol.json').read_text())
    if protocol['packet_source']!=str(ROOT/'build/signoff400/selected_full_corner_sender_packets_961'):
        raise ValueError('original predeclared campaign required')
    if (prior/'completed_corners.json').exists() or any((prior/c).exists()for c in ['ff','ss','sf','fs']) or list(prior.rglob('control.raw')):
        raise ValueError('prior campaign already launched native work; duplicate launch rejected')
    fits={c:Path(p)for c,p in protocol['fits'].items()}
    if list(fits)!=['ff','ss','sf','fs']:raise ValueError('unchanged four-corner fit order required')
    folder=Path(__file__).resolve().parent
    scripts=[folder/n for n in ['follow_selected_corner_sender_packets.py','follow_selected_full_sender_clock_frames.py','follow_selected_matching_sender_holdouts.py']]
    paths=[Path(__file__).resolve(),folder/'common_v3.py',folder/'resources.py',prior/'protocol.json',ff/'owner.json',watchdog/'owner.json',tt_frame,*scripts]
    paths += [fit/n for fit in fits.values()for n in ['assessment.json','parameters.json','detector.v']]
    pins={str(p):sha(p)for p in paths};verify(pins)
    output.mkdir();os.sched_setaffinity(0,{27});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    packets=output/'packets';frames=output/'frames';holdouts=output/'holdouts'
    save(output/'protocol.json',dict(input_sha256=pins,ff=str(ff),remaining=str(remaining),initialization_watchdog=str(watchdog),prior_unlaunched_campaign=str(prior),fits={c:str(p)for c,p in fits.items()},schedule=protocol['schedule'],packets=str(packets),frames=str(frames),holdouts=str(holdouts),maximum_serial_native_holdouts=8,new_full_native_cases=0,automatic_retry=False,parameters_refitted=False,FF_nominal_failure_resolved=False,release_ready=False))
    children=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12*86400
    def wait_ready(parents,guard):
        while not all(parent_ready(p,guard)for p in parents):
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('initialization observation deadline; parents unchanged')
            save(output/'status.json',dict(state='waiting_for_recovered_parent_initialization',parents=list(map(str,parents)),release_ready=False));time.sleep(10)
    def start(name,script,args):
        verify(pins)
        with (output/(name+'.log')).open('x')as log:
            command=['python3',str(script),*map(str,args)]
            child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        children.append((name,child));save(output/'children.json',dict(records=[dict(stage=n,pid=p.pid,birth=identity(p.pid))for n,p in children],independently_bounded=True,release_ready=False))
    try:
        wait_ready([ff,remaining],watchdog)
        start('packets',scripts[0],['--ff-pipeline',ff,'--remaining-pipeline',remaining,'--output',packets])
        wait_ready([packets],output)
        start('frames',scripts[1],['--packets',packets,'--tt-frame',tt_frame,'--output',frames])
        args=['--packets',packets,'--output',holdouts]
        for c,fit in fits.items():args+=['--'+c+'-fit',fit]
        start('holdouts',scripts[2],args)
        while any(p.poll()is None for _,p in children):
            if any(p.poll()not in(None,0)for _,p in children):raise RuntimeError('observer stopped; no automatic retry')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; bounded children unchanged')
            save(output/'status.json',dict(state='recovered_corner_observers_running',release_ready=False));time.sleep(10)
        if any(p.returncode for _,p in children):raise RuntimeError('observer failed')
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [packets/'assessment.json',frames/'assessment.json',holdouts/'assessment.json']},release_ready=False));save(output/'status.json',dict(state='recovered_corner_observers_completed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),bounded_children_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['ff','remaining','watchdog','prior','tt-frame','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve()for n in ['ff','remaining','watchdog','prior','tt-frame','output']))
