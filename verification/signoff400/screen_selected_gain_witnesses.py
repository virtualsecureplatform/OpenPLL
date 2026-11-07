"""Finite declared-gain screen against three covered stimulus witnesses."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,spec
from resources import lease,identity
from pinned_image_guard import ImageGuard
from selected_gain_screen_disposition import classify
from review_selected_frequency_stress_traces import recompute
from selected_model_registry import validate
from follow_selected_publication_matrix_v3 import result_record


def run(nominal,receiver,lower,rejections,output):
    prior=json.loads(lower.read_text());verify(prior['input_sha256'])
    rejected={(t['ki'],t['kp'])for t in prior['trials']if t['disposition']=='functional_failure'}
    if rejected!={(1,0),(1,1)}:raise ValueError('checked lower-pair failures required')
    paths=[lower];plans=[];domains=[]
    for index,root in enumerate([nominal,receiver]):
        source=root/'gain_offset_linear_period_scenario0_phase20';a=json.loads((source/'assessment.json').read_text());ci=json.loads((source/'inputs.json').read_text());verify(ci['input_sha256'])
        if classify(a)!='functional_failure':raise ValueError('covered combined-stress failure required')
        r=validate(json.loads((root/'models.json').read_text()));domains.append(r['analog_key']);clock=Path(r['interface']['clock_timing']);view='nominal'if index==0 else'receiver';cache=ROOT/'build/signoff400'/('selected_nominal_RTL_build_cache_778'if index==0 else'selected_stress_RTL_build_cache_788');detector=ROOT/'build/signoff400'/('selected_root_publication_detector_407'if index==0 else'selected_receiver_stress_detector_450')/'detector.v'
        plans.append(dict(view=view,registry=root/'models.json',clock=clock,cache=cache,detector=detector));paths.extend([source/'assessment.json',source/'inputs.json',root/'models.json',clock,cache/'assessment.json',detector])
    if domains[0]!=domains[1]:raise ValueError('same analog calibration domain required')
    # The complete KI1/KP2 and KI1/KP4 matrices each have this covered failure.
    for folder,pair in [(ROOT/'build/signoff400/selected_TT181_KI1_KP2_history_nominal_1214',(1,2)),(nominal,(1,4))]:
        a=json.loads((folder/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts']);case=folder/'gain_offset_linear_period_scenario0_phase20/assessment.json';c=json.loads(case.read_text())
        if a['gain_pair']!=list(pair)or classify(c)!='functional_failure':raise ValueError('actual covered rejection required')
        other=validate(json.loads((folder/'models.json').read_text()))
        if other['analog_key']!=domains[0]:raise ValueError('rejection from another analog domain')
        rejected.add(pair);paths.extend([folder/'assessment.json',folder/'models.json',case])
    for rejection in rejections:
        a=json.loads(rejection.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if not a.get('all_four_cases_recomputed')or len(a['records'])!=4:raise ValueError('recomputed four-view rejection required')
        if {(r['view'],r['interpolation'])for r in a['records']}!={(v,k)for v in ['nominal','receiver']for k in ['linear_period','linear_frequency']}:raise ValueError('complete rejection views required')
        states=[]
        for row in a['records']:
            case=rejection.parent/(row['view']+'_'+row['interpolation']);report=json.loads((case/'assessment.json').read_text());states.append(classify(report));ci=json.loads((case/'inputs.json').read_text());verify(ci['input_sha256']);plan=next(p for p in plans if p['view']==row['view'])
            if ci['input_sha256'].get(str(plan['registry']))!=sha(plan['registry']):raise ValueError('rejection uses another registry')
            paths.extend([case/'assessment.json',case/'inputs.json'])
        if 'functional_failure'not in states:raise ValueError('no completed gain rejection')
        rejected.add(tuple(a['gain_pair']));paths.append(rejection)
    witnesses=[('gain_offset',20),('offset',10),('nominal',10)]
    grid=spec()['gain_search'];gains=[(ki,kp)for ki in grid['ki']for kp in grid['kp']if(ki,kp)not in rejected];gains.sort()
    image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=Path(__file__).with_name('run_selected_mixed_signal_v8.py');packets=ROOT/'build/signoff400/selected_TT_frequency_stress_packets_944';folder=Path(__file__).resolve().parent;paths.extend([image,worker,*[packets/(name+'.json')for name,_ in witnesses],Path(__file__).resolve(),*[folder/n for n in ['pinned_image_guard.py','selected_gain_screen_disposition.py','selected_model_registry.py','follow_selected_publication_matrix_v3.py','acceptance_v4.py','selected_loop_assessment_v2.py','review_selected_frequency_stress_traces.py','selected_reference_phase.py']]])
    pins={str(p):sha(p)for p in paths};guard=ImageGuard(image);guard.check(pins,full=True);output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{22});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'protocol.json',dict(input_sha256=pins,ordered_gains=[list(g)for g in gains],previously_rejected_pairs=[list(g)for g in sorted(rejected)],maximum_fast_cases=12*len(gains),whole_cap_s=7200,scenario=0,witnesses=[dict(stress=n,phase_ns=p)for n,p in witnesses],native_launches=0,automatic_identical_retry=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200;records=[];candidate=None
    try:
        for ki,kp in gains:
            trials=[];disposition='pass_screen'
            for stress_name,phase in witnesses:
                for plan in plans:
                    for kind in ['linear_period','linear_frequency']:
                        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('gain screen whole-check limit')
                        guard.check(pins);case=output/f'KI{ki}_KP{kp}_{stress_name}_phase{phase}_{plan["view"]}_{kind}';args=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',worker,'--registry',plan['registry'],'--detector',plan['detector'],'--clock-timing',plan['clock'],'--build-cache',plan['cache'],'--frequency-stress',packets/(stress_name+'.json'),'--output',case,'--seed',149,'--coarse',20,'--ki',ki,'--kp',kp,'--polarity',1,'--scenario',0,'--phase-ns',phase,'--interpolation',kind];save(output/'status.json',dict(state='combined_stress_gain_case_running',gain_pair=[ki,kp],view=plan['view'],interpolation=kind,completed_pairs=len(records),stress=stress_name,phase_ns=phase,release_ready=False))
                        with lease(1,4,deadline),(output/(case.name+'.log')).open('x')as log:code=subprocess.run(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=min(180,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))).returncode
                        if code not in [0,1,3]:raise RuntimeError('incomplete worker execution')
                        a=json.loads((case/'assessment.json').read_text());checked=result_record(a,0,phase);verify(json.loads((case/'inputs.json').read_text())['input_sha256']);trials.append(dict(stress=stress_name,phase_ns=phase,view=plan['view'],interpolation=kind,assessment=str(case/'assessment.json'),assessment_sha256=sha(case/'assessment.json'),inputs=str(case/'inputs.json'),inputs_sha256=sha(case/'inputs.json'),**checked))
                        case_disposition=classify(a)
                        if case_disposition!='indeterminate_lookup':
                            passed,segments=recompute(case,0,phase)
                            if passed!=checked['functional_trace_pass']:raise ValueError('trace recomputation differs')
                            trials[-1]['recomputed_segments']=segments
                        if case_disposition!='pass_screen':disposition=case_disposition;break
                    if disposition!='pass_screen':break
                if disposition!='pass_screen':break
            records.append(dict(ki=ki,kp=kp,disposition=disposition,trials=trials));save(output/'completed_pairs.json',records)
            if disposition=='pass_screen':candidate=[ki,kp];break
        guard.check(pins,full=True);artifacts={}
        for record in records:
            for row in record['trials']:artifacts.update({str(p):sha(p)for p in Path(row['assessment']).parent.iterdir()if p.is_file()})
        verify(artifacts);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,provisional_full_sweep_candidate=candidate,witnesses=[dict(stress=n,phase_ns=p)for n,p in witnesses],previously_rejected_pairs=[list(g)for g in sorted(rejected)],full_gain_matrix_qualified=False,minimum_gain_selected=False,wide_code_stress_applicability_qualified=False,native_launches=0,image_hash_checks=guard.hash_checks,image_metadata_hits=guard.metadata_hits,release_ready=False));save(output/'status.json',dict(state='combined_stress_gain_screen_assessed',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['nominal','receiver','lower','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--rejection',type=Path,action='append',default=[]);a=p.parse_args();run(a.nominal.resolve(),a.receiver.resolve(),a.lower.resolve(),[p.resolve()for p in a.rejection],a.output.resolve())
