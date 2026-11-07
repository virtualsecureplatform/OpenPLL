"""Screen declared gains on the observed offset-stress deadline failure."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,spec
from resources import identity,lease
from follow_selected_publication_matrix_v3 import result_record


def run(nominal,receiver,output):
    if output.exists():raise FileExistsError(output)
    roots=[nominal,receiver];plans=[];paths=[]
    for index,root in enumerate(roots):
        source=root/'offset_linear_period_scenario0_phase10';report=json.loads((source/'assessment.json').read_text())
        if report['state']!='diagnostic_failed' or report['measurement_requests'] or report['scenario']!=0 or report['phase_offset_ns']!=10:
            raise ValueError('observed covered cold-start phase10 offset failure required')
        ci=json.loads((source/'inputs.json').read_text());verify(ci['input_sha256'])
        r=json.loads((root/'models.json').read_text());clock=Path(r['interface']['clock_timing']);cache=ROOT/'build/signoff400'/('selected_nominal_RTL_build_cache_778'if index==0 else'selected_stress_RTL_build_cache_788')
        detector=ROOT/'build/signoff400'/('selected_root_publication_detector_407'if index==0 else'selected_receiver_stress_detector_450')/'detector.v'
        paths += [source/'assessment.json',source/'inputs.json',source/'segment0_acceptance.json',root/'models.json',clock,cache/'assessment.json',detector]
        plans.append(dict(name='nominal'if index==0 else'receiver',registry=root/'models.json',clock=clock,cache=cache,detector=detector))
    gains=[k for k in spec()['gain_search']['ki']if k>1]
    if gains!=[2,4,8,16]or 8 not in spec()['gain_search']['kp']:raise ValueError('declared ordered gain grid required')
    folder=Path(__file__).resolve().parent;worker=folder/'run_selected_mixed_signal_v8.py';image=ROOT/'build/apptainer/openpll-release-modern.sif';stress=ROOT/'build/signoff400/selected_TT_frequency_stress_packets_944/offset.json'
    paths += [Path(__file__).resolve(),worker,image,stress,*[folder/n for n in ['common_v3.py','resources.py','follow_selected_publication_matrix_v3.py','acceptance_v4.py','selected_loop_assessment_v2.py']]]
    pins={str(p):sha(p)for p in paths};verify(pins);output.mkdir();os.sched_setaffinity(0,{22});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    save(output/'protocol.json',dict(input_sha256=pins,gains=[[k,8]for k in gains],timing_variants=['nominal','receiver'],scenario=0,phase_ns=10,interpolation='linear_period',seed_fine=149,maximum_fast_cases=8,new_native_cases=0,selection_from_screen_is_not_full_matrix_qualification=True,release_ready=False))
    records=[]
    try:
        for ki in gains:
            for plan in plans:
                verify(pins);case=output/('%s_KI%d_KP8'%(plan['name'],ki));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+240
                command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'python3',worker,'--registry',plan['registry'],'--detector',plan['detector'],'--clock-timing',plan['clock'],'--build-cache',plan['cache'],'--frequency-stress',stress,'--output',case,'--seed',149,'--coarse',20,'--ki',ki,'--kp',8,'--polarity',1,'--scenario',0,'--phase-ns',10,'--interpolation','linear_period']
                save(output/'status.json',dict(state='offset_acquisition_gain_case_running',ki=ki,timing=plan['name'],completed_cases=len(records),release_ready=False))
                with lease(1,4,deadline),(output/(case.name+'.log')).open('x')as log:
                    code=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
                if code not in [0,1,3]:raise RuntimeError('case execution failed')
                report=case/'assessment.json';a=json.loads(report.read_text());checked=result_record(a,0,10);inputs=case/'inputs.json';verify(json.loads(inputs.read_text())['input_sha256'])
                records.append(dict(ki=ki,kp=8,timing=plan['name'],assessment=str(report),sha256=sha(report),inputs=str(inputs),inputs_sha256=sha(inputs),**checked));save(output/'completed_cases.json',records)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={**{r['assessment']:r['sha256']for r in records},**{r['inputs']:r['inputs_sha256']for r in records}},records=records,full_gain_matrix_qualified=False,minimum_gain_selected=False,release_ready=False));save(output/'status.json',dict(state='offset_acquisition_gain_screen_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['nominal','receiver','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.nominal.resolve(),a.receiver.resolve(),a.output.resolve())
