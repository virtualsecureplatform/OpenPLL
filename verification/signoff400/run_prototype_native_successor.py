"""Queue one changed native operating point after a successful, identity-checked predecessor."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import time
from common import save,sha,verify
from compiled_charge import execute
from resources import identity,lease
from assess_prototype_native_waveform import run as assess_waveform


def changed_command(command,output,corner,coarse,fine,step,reltol):
    result=list(command)
    updates={'--corner':corner,'--coarse-codes':str(coarse),'--codes':str(fine),
             '--max-step-ps':str(step),'--ngspice-reltol':str(reltol)}
    if not 0<=coarse<=47 or not 0<=fine<=255 or not 0<step<=10 or not 0<reltol<=1e-5:
        raise ValueError('unsupported native point or weaker numerical controls')
    if corner not in ('tt','ff','ss','sf','fs'):raise ValueError('unsupported corner')
    if '--ngspice-waveform' not in result:raise ValueError('waveform-producing predecessor required')
    changed=False
    for key,value in updates.items():
        i=result.index(key)+1
        old=result[i]
        changed|=(float(old)!=float(value)) if key!='--corner' else old!=value
        result[i]=value
    if not changed:raise ValueError('identical native retry is prohibited')
    result[result.index('--build-dir')+1]=str(output/'native')
    return result


def run(predecessor,output,corner,coarse,fine,step,reltol,purpose):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',
                      MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1',GOMAXPROCS='1')
    manifest=predecessor/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    command=changed_command(m['command'],output,corner,coarse,fine,step,reltol)
    receipt=predecessor/'assessment.json'
    def state(value,**kwargs):save(output/'status.json',dict(state=value,release_ready=False,**kwargs))
    state('waiting_for_successful_predecessor')
    try:
        while True:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('successor deadline exhausted')
            status=json.loads((predecessor/'status.json').read_text())
            process=json.loads((predecessor/'owner.json').read_text())
            live=identity(process['pid'])==process['birth']
            if status['state']=='stopped_without_promotion':raise ValueError('predecessor failed; no successor launched')
            if receipt.exists() and not live:break
            if not live:raise ValueError('predecessor disappeared without completed evidence')
            time.sleep(1)
        r=json.loads(receipt.read_text())
        if r.get('native_worker_completed') is not True:raise ValueError('predecessor not successful')
        verify(r['input_sha256'])
        rows=list(csv.DictReader((predecessor/'native/dco_postlayout_results.csv').open()))
        if len(rows)!=1 or rows[0]['status']!='pass':raise ValueError('predecessor metrics failed')
        # Use the full-window measurement check, not just the legacy two-cycle CSV.
        assess_waveform(predecessor,output/'predecessor_waveform_review')
        native=output/'native';native.mkdir();init=native/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
        pins=dict(m['input_sha256'])
        for p in (manifest,receipt,init,Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_native_waveform.py')):
            pins[str(p)]=sha(p)
        save(output/'input_manifest.json',dict(input_sha256=pins,command=command,purpose=purpose,
             diagnostic=True,interconnect_corner=m.get('interconnect_corner'),parent_loading_complete=False))
        # Successor jobs share one native slot in addition to aggregate CPU/RAM leases.
        lockpath=output.parent/'resources/prototype_native_successor.lock';lockpath.parent.mkdir(exist_ok=True)
        with lockpath.open('a+') as lock:
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native slot deadline')
                    state('waiting_for_native_slot');time.sleep(1)
            state('waiting_for_native_resource_lease')
            with lease(1,16,deadline):
                state('native_successor_running')
                execute(command,output/'native.log',deadline,16)
                verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,native_worker_completed=True,
             diagnostic=True,validated_for_prototype=False,final_loading_parasitics_complete=False,
             release_ready=False,production_qualified=False))
        assess_waveform(output,output/'all_cycle_assessment')
        state('native_successor_complete_review_pending')
    except BaseException as error:
        state('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--predecessor',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True)
    p.add_argument('--coarse',type=int,required=True);p.add_argument('--fine',type=int,required=True)
    p.add_argument('--max-step-ps',type=float,default=10);p.add_argument('--reltol',type=float,default=1e-5)
    p.add_argument('--purpose',required=True)
    a=p.parse_args();run(a.predecessor.resolve(),a.output.resolve(),a.corner,a.coarse,a.fine,a.max_step_ps,a.reltol,a.purpose)
