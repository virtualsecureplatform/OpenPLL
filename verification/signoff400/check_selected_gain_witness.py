"""Check one declared diagnostic gain/stimulus witness across four cached views."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,spec
from resources import identity,lease
from pinned_image_guard import ImageGuard
from selected_gain_screen_disposition import classify
from selected_model_registry import validate
from follow_selected_publication_matrix_v3 import result_record
from review_selected_frequency_stress_traces import recompute


def run(nominal,receiver,ki,kp,stress,scenario,phase,output):
    grid=spec()['gain_search']
    if ki not in grid['ki']or kp not in grid['kp']or stress not in ['nominal','gain','offset','gain_offset']or scenario not in range(3)or phase not in [0,10,20,30]:raise ValueError('declared gain/stimulus required')
    paths=[];plans=[];domains=[]
    for index,root in enumerate([nominal,receiver]):
        receipt=root/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['completed_cases']!=96:raise ValueError('complete source sensitivity matrix required')
        source=root/f'{stress}_linear_period_scenario{scenario}_phase{phase}';a=json.loads((source/'assessment.json').read_text())
        if classify(a)=='indeterminate_lookup':raise ValueError('covered source stimulus required')
        verify(json.loads((source/'inputs.json').read_text())['input_sha256']);registry=root/'models.json';model=validate(json.loads(registry.read_text()));domains.append(model['analog_key']);clock=Path(model['interface']['clock_timing']);cache=ROOT/'build/signoff400'/('selected_nominal_RTL_build_cache_778'if index==0 else'selected_stress_RTL_build_cache_788');detector=ROOT/'build/signoff400'/('selected_root_publication_detector_407'if index==0 else'selected_receiver_stress_detector_450')/'detector.v'
        plans.append(dict(view='nominal'if index==0 else'receiver',registry=registry,clock=clock,cache=cache,detector=detector));paths.extend([receipt,source/'assessment.json',source/'inputs.json',registry,clock,cache/'assessment.json',detector])
    if domains[0]!=domains[1]:raise ValueError('same analog calibration domain required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=Path(__file__).with_name('run_selected_mixed_signal_v8.py');packet=ROOT/'build/signoff400/selected_TT_frequency_stress_packets_944'/(stress+'.json');folder=Path(__file__).resolve().parent;paths.extend([image,worker,packet,Path(__file__).resolve(),*[folder/n for n in ['pinned_image_guard.py','selected_gain_screen_disposition.py','selected_model_registry.py','follow_selected_publication_matrix_v3.py','review_selected_frequency_stress_traces.py','acceptance_v4.py','selected_reference_phase.py']]])
    pins={str(p):sha(p)for p in paths};guard=ImageGuard(image);guard.check(pins,full=True);output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{22});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'protocol.json',dict(input_sha256=pins,gain_pair=[ki,kp],stress=stress,scenario=scenario,phase_ns=phase,CPU=22,maximum_fast_cases=4,native_launches=0,automatic_identical_retry=False,release_ready=False));records=[];artifacts={};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        for plan in plans:
            for kind in ['linear_period','linear_frequency']:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('four-case witness limit')
                guard.check(pins);case=output/(plan['view']+'_'+kind);args=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',worker,'--registry',plan['registry'],'--detector',plan['detector'],'--clock-timing',plan['clock'],'--build-cache',plan['cache'],'--frequency-stress',packet,'--output',case,'--seed',149,'--coarse',20,'--ki',ki,'--kp',kp,'--polarity',1,'--scenario',scenario,'--phase-ns',phase,'--interpolation',kind];save(output/'status.json',dict(state='gain_witness_case_running',completed_cases=len(records),view=plan['view'],interpolation=kind,release_ready=False))
                with lease(1,4,deadline),(output/(case.name+'.log')).open('x')as log:code=subprocess.run(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=min(180,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))).returncode
                if code not in [0,1,3]:raise RuntimeError('worker execution incomplete')
                a=json.loads((case/'assessment.json').read_text());checked=result_record(a,scenario,phase);disposition=classify(a);verify(json.loads((case/'inputs.json').read_text())['input_sha256']);before={str(p):sha(p)for p in case.iterdir()if p.is_file()};segments=None
                if disposition!='indeterminate_lookup':
                    passed,segments=recompute(case,scenario,phase)
                    if passed!=checked['functional_trace_pass']:raise ValueError('recomputed trace disposition differs')
                verify(before);artifacts.update(before);records.append(dict(view=plan['view'],interpolation=kind,strict_disposition=disposition,segments=segments,**checked));save(output/'completed_cases.json',records)
        guard.check(pins,full=True);verify(artifacts);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,gain_pair=[ki,kp],stress=stress,scenario=scenario,phase_ns=phase,records=records,all_four_cases_recomputed=all(r['segments']is not None for r in records),all_four_pass=all(r['strict_disposition']=='pass_screen'for r in records),full_gain_matrix_qualified=False,minimum_gain_selected=False,physical_models_qualified=False,release_ready=False));save(output/'status.json',dict(state='gain_witness_assessed',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['nominal','receiver','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--ki',type=int,required=True);p.add_argument('--kp',type=int,required=True);p.add_argument('--stress',choices=['nominal','gain','offset','gain_offset'],required=True);p.add_argument('--scenario',type=int,choices=range(3),required=True);p.add_argument('--phase-ns',type=int,choices=[0,10,20,30],required=True);a=p.parse_args();run(a.nominal.resolve(),a.receiver.resolve(),a.ki,a.kp,a.stress,a.scenario,a.phase_ns,a.output.resolve())
