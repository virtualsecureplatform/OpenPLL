"""Queue one diagnostic sensitivity matrix after a checked predecessor completes."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,spec
from resources import identity


def run(after,pipeline,composition,cache,packets,cpu,ki,kp,output):
    if ki not in spec()['gain_search']['ki']or kp not in spec()['gain_search']['kp']:raise ValueError('declared gain required')
    source=after/'inputs.json';prior=json.loads(source.read_text());verify(prior['input_sha256']);owner=json.loads((after/'owner.json').read_text());worker=Path(__file__).with_name('follow_selected_frequency_stress_matrix_v4.py');image=ROOT/'build/apptainer/openpll-release-modern.sif'
    files=[source,after/'owner.json',pipeline/'selected_interface/models.json',composition/'assessment.json',composition/'detector.v',cache/'assessment.json',image,worker,Path(__file__).resolve(),Path(__file__).with_name('pinned_image_guard.py'),*[packets/(n+'.json')for n in ['nominal','gain','offset','gain_offset']]];pins={str(p):sha(p)for p in files};verify(pins)
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,predecessor_owner=owner,predecessor=str(after),gain_pair=[ki,kp],CPU=cpu,max_fast_cases=96,native_launches=0,queue_cap_s=7200,child_independently_bounded=True,automatic_identical_retry=False,release_ready=False))
    child=None
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
        while True:
            state=json.loads((after/'status.json').read_text())['state']
            if state=='diagnostic_frequency_stress_matrix_assessed':break
            if state=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:raise RuntimeError('predecessor stopped without completed matrix')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('predecessor observation limit')
            save(output/'status.json',dict(state='waiting_for_predecessor_matrix',release_ready=False));time.sleep(10)
        proof=after/'assessment.json';r=json.loads(proof.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['completed_cases']!=96 or r['expected_cases']!=96:raise ValueError('complete predecessor required')
        pins[str(proof)]=sha(proof);verify(pins);destination=output/'matrix'
        args=['/usr/bin/python3',worker,'--pipeline',pipeline,'--composition',composition,'--cache',cache,'--packets',packets,'--cpu',cpu,'--ki',ki,'--kp',kp,'--output',destination]
        with(output/'matrix.log').open('x')as log:child=subprocess.Popen(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(output/'child.json',dict(pid=child.pid,birth=identity(child.pid),independently_bounded=True));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180000
        while child.poll()is None:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('child observation limit; independently bounded child untouched')
            save(output/'status.json',dict(state='followup_matrix_running',release_ready=False));time.sleep(10)
        if child.returncode:raise RuntimeError('followup stopped; no identical retry')
        result=destination/'assessment.json';r=json.loads(result.read_text());verify(r['input_sha256']);verify(r['artifacts']);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(result):sha(result)},completed_cases=r['completed_cases'],gain_pair=[ki,kp],full_physical_qualification=False,release_ready=False));save(output/'status.json',dict(state='followup_matrix_assessed',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),existing_jobs_and_independently_bounded_child_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['after','pipeline','composition','cache','packets','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=[23,24],required=True);p.add_argument('--ki',type=int,required=True);p.add_argument('--kp',type=int,required=True);a=p.parse_args();run(a.after.resolve(),a.pipeline.resolve(),a.composition.resolve(),a.cache.resolve(),a.packets.resolve(),a.cpu,a.ki,a.kp,a.output.resolve())
