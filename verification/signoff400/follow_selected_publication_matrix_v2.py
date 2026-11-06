"""Run the declared scenario/phase matrix after native calibration is available.

Uses actual selected RTL and existing diagnostic interpolation/publication models.
No native launch, extrapolation, analog qualification or release promotion occurs.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify,spec
from selected_physical_rtl import source_pins
from selected_model_registry import validate
from resources import identity,lease
from selected_mixed_signal_build_cache_v2 import fingerprint

KINDS=('linear_period','linear_frequency')

def result_record(report,scenario,phase):
    if report.get('scenario')!=scenario or report.get('phase_offset_ns')!=phase:
        raise ValueError('actual report scenario/phase differs from requested case')
    if report.get('diagnostic')is not True or report.get('physical_models_qualified')is not False or report.get('release_ready')is not False:
        raise ValueError('explicit diagnostic model scope required')
    state=report['state']
    if state not in ('needs_native_tuning_points','diagnostic_simulation_completed','diagnostic_failed'):
        raise ValueError('unsupported terminal diagnostic state')
    functional=(state=='diagnostic_simulation_completed'and report.get('functional_trace_pass')is True
                and report.get('reference_phase_coverage_pass')is True and report.get('native_exit')==0
                and report.get('terminal_marker_present')is True)
    return dict(state=state,functional_trace_pass=functional,
        reference_phase_coverage_pass=report.get('reference_phase_coverage_pass')is True,
        measurement_requests=report.get('measurement_requests',[]))

def run(pipeline,composition,output,cpu=16,build_cache=None,ki=None,kp=None):
    if build_cache is None:raise ValueError('verified shared compiled build required')
    if cpu not in range(16,32):raise ValueError('spare physical CPU required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif';image_stamp=fingerprint(image)
    owner=json.loads((pipeline/'owner.json').read_text());profile=spec()
    ki=profile['gain_search']['first'][0]if ki is None else ki
    kp=profile['gain_search']['first'][1]if kp is None else kp
    if type(ki)is not int or type(kp)is not int or ki not in profile['gain_search']['ki']or kp not in profile['gain_search']['kp']:raise ValueError('gain pair must belong to declared search grid')
    receipt=composition/'assessment.json';c=json.loads(receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    pins=source_pins();pins.update(c['input_sha256']);pins.update(c['artifacts'])
    paths=[Path(__file__).resolve(),folder/'run_selected_mixed_signal_v6.py',folder/'selected_frequency_interpolation.py',folder/'selected_model_registry.py',folder/'resources.py',folder/'common_v3.py',PROFILE,image,pipeline/'owner.json',receipt,build_cache/'assessment.json',folder/'selected_mixed_signal_build_cache_v2.py']
    pins.update({str(p):sha(p)for p in paths})
    def check_pins():
        verify({p:d for p,d in pins.items()if p!=str(image)})
        if fingerprint(image)!=image_stamp:raise ValueError('image changed since checksum verification')
    check_pins()
    save(output/'inputs.json',dict(input_sha256=pins,original_owner=owner,automatic_native_launch=False,
        scenario_names=profile['scenarios'],phases_ns=profile['reference_phase_offsets_ns'],interpolation_variants=KINDS,
        gain_pair=[ki,kp],build_cache=str(build_cache),diagnostic=True,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+176400
    try:
        registry=pipeline/'selected_interface/models.json'
        while not registry.exists():
            state=json.loads((pipeline/'status.json').read_text())['state']
            if state=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:
                raise RuntimeError('original calibration stopped before model registry')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_native_calibration',release_ready=False));time.sleep(10)
        r=validate(json.loads(registry.read_text()))
        if r['analog']['operating_point']!=c['operating_point']:raise ValueError('composition/calibration operating points differ')
        points=[p for p in r['points']if p['coarse']==20]
        if not points:raise ValueError('measured coarse20 startup point required')
        point=min(points,key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))
        clock=Path(r['interface']['clock_timing']);detector=composition/'detector.v'
        pins.update(r['analog']['input_sha256']);pins.update({str(p):sha(p)for p in (registry,clock)})
        for p in points:pins[p['receipt']]=sha(Path(p['receipt']))
        check_pins();records=[]
        expected={(kind,index,phase)for kind in KINDS for index in range(len(profile['scenarios']))for phase in profile['reference_phase_offsets_ns']}
        matrix_started=time.monotonic()
        for kind,index,phase in sorted(expected):
            name=profile['scenarios'][index];dest=output/f'{kind}_{name}_phase{phase}'
            command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',folder/'run_selected_mixed_signal_v6.py',
                '--detector',detector,'--clock-timing',clock,'--output',dest,'--coarse',20,'--seed',point['fine'],
                '--ki',ki,'--kp',kp,'--polarity',1,'--scenario',index,'--phase-ns',phase,'--interpolation',kind,'--build-cache',build_cache]
            for p in points:command+=['--point',p['receipt']]
            save(output/'status.json',dict(state='scenario_phase_matrix_running',completed_cases=len(records),expected_cases=len(expected),current_case=[kind,name,phase],release_ready=False))
            with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
                with (output/(dest.name+'.log')).open('x')as log:
                    result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=180)
            assessment=dest/'assessment.json'
            if result.returncode not in (0,1,3)or not assessment.exists():raise RuntimeError('case failed without diagnostic assessment')
            report=json.loads(assessment.read_text());record=result_record(report,index,phase)
            inputs=dest/'inputs.json';case_inputs=json.loads(inputs.read_text());verify(case_inputs['input_sha256'])
            if case_inputs.get('compiled_build_reused')is not True or case_inputs.get('build_cache')!=str(build_cache)or case_inputs.get('runtime_namespace_checked_by_cache_loader')is not True:raise ValueError('verified shared build was not used')
            selected=source_pins()
            if any(case_inputs['input_sha256'].get(p)!=d for p,d in selected.items()):raise ValueError('case not bound to selected physical RTL')
            record.update(interpolation=kind,scenario=index,scenario_name=name,phase_ns=phase,assessment=str(assessment),assessment_sha256=sha(assessment),inputs=str(inputs),inputs_sha256=sha(inputs))
            records.append(record);check_pins()
        if {(x['interpolation'],x['scenario'],x['phase_ns'])for x in records}!=expected or len(records)!=len(expected):
            raise ValueError('complete unique scenario/phase/variant matrix required')
        requests=sorted({(q['coarse'],q['fine'])for x in records for q in x['measurement_requests']})
        artifacts={x['assessment']:x['assessment_sha256']for x in records};artifacts.update({x['inputs']:x['inputs_sha256']for x in records});verify(artifacts)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,compiled_build_reused=True,matrix_execution_wall_s=time.monotonic()-matrix_started,artifacts=artifacts,records=records,expected_cases=len(expected),
            declared_scenario_phase_matrix_executed=True,selected_measured_point=point,ki=ki,kp=kp,
            diagnostic_functional_pass_count=sum(x['functional_trace_pass']for x in records),
            requested_native_points=[dict(coarse=c,fine=f)for c,f in requests],
            scope='One operating point, all declared scenarios/phases, two interpolation estimates, actual selected RTL. Publication timing and interpolation errors remain unqualified.',
            native_correlated_controller_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='scenario_phase_matrix_assessed',completed_cases=len(records),release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('pipeline','composition','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=range(16,32),default=16)
    p.add_argument('--build-cache',type=Path,required=True);p.add_argument('--ki',type=int);p.add_argument('--kp',type=int);a=p.parse_args()
    run(*(getattr(a,n).resolve()for n in ('pipeline','composition','output')),a.cpu,a.build_cache.resolve(),a.ki,a.kp)
