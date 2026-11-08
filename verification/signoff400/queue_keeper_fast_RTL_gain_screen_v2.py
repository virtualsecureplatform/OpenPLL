"""Fresh TT gain diagnostics using native measurements at the prior final-code interval."""
import contextlib,json,os,time
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify,spec
from resources import identity,lease
from selected_static_DCO_point import measured_point
from run_selected_mixed_signal_v11 import run as simulate


from queue_keeper_fast_RTL_gain_screen import gain_order,candidate


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_native_grid_RTL_gain_screen_1561'
    output.mkdir(exist_ok=False);(output/'cases').mkdir()
    os.sched_setaffinity(0,{24})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    target=base/'selected_keeper_static_target_DCO_1549'
    plan=base/'selected_keeper_final_code_validation_plan_1556/plan.json'
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    if p['fit_codes']!=[128,149] or p['validation_codes']!=[129,130,131]:
        raise ValueError('three predeclared final-code native points required')
    targets=[Path(c['output']) for c in p['cases']]
    profile=spec();order=gain_order(profile)
    detector=base/'selected_root_publication_detector_407/detector.v'
    clock=base/'selected_clock_phase_observations_187.json'
    cache=base/'selected_nominal_RTL_build_cache_778'
    receipts=[base/'selected_keeper_static_coarse23_fine8_DCO_1545/assessment.json',
              target/'assessment.json',base/'selected_keeper_static_coarse23_DCO_1541/assessment.json']
    receipts.extend(t/'assessment.json' for t in targets)
    dependencies=[Path(__file__).resolve(),PROFILE,plan,target/'inputs.json',detector,clock,cache/'assessment.json']
    dependencies.extend(t/'inputs.json' for t in targets)
    dependencies.append(Path(__file__).with_name('queue_keeper_fast_RTL_gain_screen.py'))
    dependencies += [Path(__file__).with_name(n) for n in ('run_selected_mixed_signal_v11.py',
          'selected_static_DCO_point.py','selected_loop_assessment_v3.py','acceptance_v5.py')]
    pins={str(p):sha(p) for p in dependencies}
    save(output/'inputs.json',dict(input_sha256=pins,scope='TT27C1.8V actual-RTL diagnostics with unqualified static DCO/detector/timing models',
         coarse=23,seed=128,native_knots=[8,128,129,130,131,149],prior_gain_screen_modified=False,gain_order=order,scenarios=profile['scenarios'],phases_ns=profile['reference_phase_offsets_ns'],
         maximum_cases=300,one_case_at_a_time=True,CPU=24,memory_GiB=2,
         observation_cap_s=86400,screen_cap_s=1800,automatic_identical_retry=False,
         lower_gain_unresolved_blocks_candidate=True,release_gain_selection=False,release_ready=False))
    try:
        deadline=time.monotonic()+86400
        while True:
            pending=[]
            for native in targets:
                state=json.loads((native/'status.json').read_text())['state']
                if state=='static_terminated_DCO_capture_complete':continue
                if state=='stopped_without_qualification':raise RuntimeError('native final-code capture stopped')
                owner=json.loads((native/'owner.json').read_text())
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native final-code owner missing')
                pending.append(str(native))
            if not pending:break
            if time.monotonic()>=deadline:raise TimeoutError('native final-code observation cap')
            save(output/'status.json',dict(state='waiting_for_completed_native_grid',pending=pending,release_ready=False));time.sleep(10)
        if measured_point(receipts[1])[:2]!=(23,128):raise ValueError('completed target code differs')
        for receipt in receipts:
            measured_point(receipt);pins[str(receipt)]=sha(receipt)
        if {measured_point(r)[:2] for r in receipts}!={(23,f) for f in (8,128,129,130,131,149)}:
            raise ValueError('exact six-point native code grid required')
        verify(pins)
        gains=[];cases=[];start=time.monotonic()
        for ki,kp in order:
            outcome='all_TT_diagnostic_cases_pass';executed=[]
            for scenario,name in enumerate(profile['scenarios']):
                for phase in profile['reference_phase_offsets_ns']:
                    if time.monotonic()-start>=1800:raise TimeoutError('bounded TT screen cap')
                    case=output/'cases'/f'KI{ki}_KP{kp}_{name}_phase{phase}'
                    save(output/'status.json',dict(state='running_TT_diagnostic_case',ki=ki,kp=kp,scenario=name,phase_ns=phase,release_ready=False))
                    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
                        with case.with_suffix('.log').open('x') as log,contextlib.redirect_stdout(log):
                            result=simulate(receipts,detector,case,ki=ki,kp=kp,coarse=23,seed=128,
                                polarity=1,scenario=scenario,phase_ns=phase,clock_timing_path=clock,
                                interpolation_kind='linear_frequency',build_cache=cache)
                    row=dict(ki=ki,kp=kp,scenario=name,phase_ns=phase,state=result['state'],
                        functional_trace_pass=result['functional_trace_pass'],measurement_requests=result['measurement_requests'],
                        receipt=str(case/'assessment.json'))
                    cases.append(row);executed.append(row)
                    if result['state']=='needs_native_tuning_points':outcome='unresolved_model_support';break
                    if result['native_exit']!=0 or not result['terminal_marker_present']:
                        raise RuntimeError('incomplete diagnostic infrastructure execution')
                    if not result['functional_trace_pass']:outcome='diagnostic_failure';break
                if outcome!='all_TT_diagnostic_cases_pass':break
            gains.append(dict(ki=ki,kp=kp,state=outcome,cases_executed=len(executed)))
            save(output/'progress.json',dict(gains=gains,cases=cases,TT_diagnostic_candidate=candidate(gains,order),release_ready=False))
            if candidate(gains,order) is not None:break
        verify(pins)
        artifacts=[output/'inputs.json',output/'progress.json',*[Path(c['receipt']) for c in cases],
                   *[p for p in (output/'cases').iterdir() if p.suffix=='.log']]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},
             gains=gains,cases_executed=len(cases),TT_diagnostic_candidate=candidate(gains,order),
             all_corners_checked=False,analog_models_qualified=False,release_gain_selected=False,release_ready=False))
        save(output/'status.json',dict(state='bounded_TT_diagnostic_screen_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':run()
