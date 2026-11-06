"""Capture a queued serial native process once it is actually executing Xyce."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from capture_selected_phase_runtime_group import run as capture


def run(case,reference,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31});owner=json.loads((case/'owner.json').read_text())
    files=[Path(__file__).resolve(),Path(__file__).with_name('capture_selected_phase_runtime_group.py'),Path(__file__).with_name('capture_selected_native_runtime.py'),reference,image,case/'owner.json'];pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,case=str(case),original_owner=owner,automatic_native_launch=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            handle=case/'native.process.json';manifest=case/'manifest.json'
            if handle.exists() and manifest.exists():
                worker=json.loads(handle.read_text());m=json.loads(manifest.read_text())
                if m.get('MPI_ranks',1)!=1:raise ValueError('serial native capture required; use the full-MPI capture for full jobs')
                expected=[p for p in m['input_sha256'] if p.endswith('/Xyce')]
                if len(expected)!=1:raise ValueError('unique pinned Xyce executable required')
                if identity(worker['pid'])!=str(worker['birth']):raise RuntimeError('original worker exited before live runtime capture')
                try:executable=os.readlink(f'/proc/{worker["pid"]}/exe')
                except FileNotFoundError:executable=''
                if executable==expected[0]:break
            if identity(owner['pid'])!=str(owner['birth']):raise RuntimeError('original owner exited before native admission')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('runtime observation deadline; original native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_serial_Xyce_process',release_ready=False));time.sleep(1)
        verify(pins)
        with lease(1,1,deadline):capture([case],reference,image,output/'runtime.json')
        verify(pins);report=output/'runtime.json';r=json.loads(report.read_text())
        if not r['all_live_dependencies_match_reference']:raise ValueError('native runtime differs from pinned dependency reference')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},all_live_dependencies_match_reference=True,automatic_native_launch=False,release_ready=False));save(output/'status.json',dict(state='original_serial_native_runtime_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['case','reference','image','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['case','reference','image','output']))
