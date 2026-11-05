"""Audit the complete common-gain diagnostic matrix and its actual final windows."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import PROFILE,save,sha,verify
from resources import lease

def window_pass(window,profile):
    period=1000/profile['target_mhz']
    return bool(window['frequency_error_ppm']<=profile['frequency_error_ppm'] and
        window['phase_span_ns']<=period*profile['phase_span_output_periods'] and
        abs(window['phase_mean_ns'])<=period*profile['phase_mean_output_periods'] and
        abs(window['phase_drift_ns'])<=period*profile['phase_drift_output_periods'] and
        not window['cycle_slip'] and not any(window['cycle_gaps'].values()) and
        not window['fine_outside_operating_range'] and
        profile['fine_code_min']<=window['fine_min']<=window['fine_max']<=profile['fine_code_max'])

def run(candidate,loops,controls,output):
    profile=json.loads(PROFILE.read_text());authority=candidate/'assessment.json';c=json.loads(authority.read_text())
    pins={str(p):sha(p) for p in (PROFILE,authority,Path(__file__).resolve())}
    def merge(values):
        for name,digest in values.items():
            if name in pins and pins[name]!=digest:raise ValueError('conflicting evidence digest')
            pins[name]=digest
    merge(c['artifacts']);merge(c['candidate_source_sha256'])
    sources=None;gain=None;corners=set();results=[];behavior_by_corner={}
    def behavior(record):
        files={p:d for p,d in record["input_sha256"].items() if p.endswith(("/models.json","/dco_table.txt","/detector.v","/parameters.json","/tb_programmed400_closed_loop.v","/phase_clock_vpi.cpp","/phase_clock.h","/phase_clock_shaped_vpi.cpp","/phase_clock_shaped.h"))}
        shaped=any(p.endswith('/phase_clock_shaped_vpi.cpp') for p in files)
        duty=record.get('dco_fixed_duty_ppm')
        if shaped and (not isinstance(duty,int) or not 0<duty<1000000):
            raise ValueError('shaped bridge requires explicit valid duty configuration')
        return files,duty
    for loop in loops:
        receipt=loop/'assessment.json';a=json.loads(receipt.read_text());merge({str(receipt):sha(receipt)});merge(a['input_sha256']);merge(a['artifacts'])
        actual=a['candidate_source_sha256']
        if not a['exact_synthesized_candidate_sources_executed'] or any(c['candidate_source_sha256'].get(p)!=digest for p,digest in actual.items()):
            raise ValueError('exact selected candidate execution required')
        if sources is None:sources=actual
        elif sources!=actual:raise ValueError('candidate RTL identities differ across corners')
        current=(a['ki'],a['kp'])
        if gain is None:gain=current
        elif gain!=current:raise ValueError('one common gain pair required')
        if a['profile_sha256']!=sha(PROFILE) or a['corner'] in corners:raise ValueError('profile mismatch or duplicate corner')
        corners.add(a['corner'])
        behavior_by_corner[a["corner"]]=behavior(a)
        expected={(s,p) for s in profile['scenarios'] for p in profile['reference_phase_offsets_ns']}
        if len(a['records'])!=12 or {(r['scenario'],r['phase_offset_ns']) for r in a['records']}!=expected:
            raise ValueError('complete twelve-case corner matrix required')
        windows=[];acquisition=[]
        for record in a['records']:
            if record['native_exit']!=0 or not record['passed']:raise ValueError('all native diagnostic cases must pass')
            segments=record['segments'];count=1 if record['scenario']=='cold_start' else 2
            if len(segments)!=count or {r['segment'] for r in segments}!=set(range(count)):raise ValueError('complete recovery segments required')
            for segment in segments:
                path=loop/f'{record["scenario"]}_phase{record["phase_offset_ns"]}'/f'segment{segment["segment"]}.json'
                if a['artifacts'].get(str(path))!=sha(path):raise ValueError('unbound segment observation')
                data=json.loads(path.read_text());final=data['windows'][-profile['sustained_windows']:]
                delay=data['acquisition_confirmed_ns']-data['stimulus_ns']
                if not data['complete_control_trace_checked'] or not data['sustained_final_pass'] or len(final)!=4 or not all(window_pass(w,profile) for w in final) or not 0<=delay<=profile['acquisition_limit_ns']:
                    raise ValueError('direct final-window or acquisition criterion failed')
                windows.extend(final);acquisition.append(delay)
        results.append(dict(corner=a['corner'],cases=12,segments=len(acquisition),final_windows=len(windows),
             maximum_acquisition_ns=max(acquisition),maximum_phase_span_ns=max(w['phase_span_ns'] for w in windows),
             maximum_absolute_phase_mean_ns=max(abs(w['phase_mean_ns']) for w in windows),
             maximum_absolute_phase_drift_ns=max(abs(w['phase_drift_ns']) for w in windows),
             maximum_frequency_error_ppm=max(w['frequency_error_ppm'] for w in windows),
             steady_fine_range=[min(w['fine_min'] for w in windows),max(w['fine_max'] for w in windows)]))
    if corners!=set(profile['corners']):raise ValueError('all five corners required')
    if gain[0]!=min(profile['gain_search']['ki']) or gain[1] not in profile['gain_search']['kp']:
        raise ValueError('selected gain must be in declared search at its lowest integral gain')
    rejected=set()
    for directory in controls:
        receipt=directory/'assessment.json';a=json.loads(receipt.read_text());merge({str(receipt):sha(receipt)});merge(a['input_sha256']);merge(a['artifacts'])
        if a['candidate_source_sha256']!=sources or a['ki']!=gain[0] or a['profile_sha256']!=sha(PROFILE):raise ValueError('lower-gain control source differs')
        if a['corner'] not in behavior_by_corner or behavior(a)!=behavior_by_corner[a['corner']]:raise ValueError('lower-gain control must use the same tuning, detector and startup models')
        if any(r['native_exit']!=0 for r in a['records']) or not any(not r['passed'] and any(not s['passed'] for s in r['segments']) for r in a['records']):
            raise ValueError('lower-gain rejection must be a completed trace failure')
        rejected.add(a['kp'])
    if rejected!={kp for kp in profile['gain_search']['kp'] if kp<gain[1]}:
        raise ValueError('all smaller proportional gains need an actual failing case')
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+43200):verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'corners.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},candidate_source_sha256=sources,
         ki=gain[0],kp=gain[1],completed_cases=60,completed_recovery_segments=100,independently_checked_final_windows=400,
         all_diagnostic_trace_criteria_pass=True,smaller_proportional_gains_rejected=sorted(rejected),
         selected_gain_minimal_in_nominal_diagnostic_search=True,physical_models_qualified=False,
         native_holdout_and_parent_loading_uncertainty_bounded=False,closed_loop_operation_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('loop','lower-gain-control'):parser.add_argument('--'+name,type=Path,required=True,action='append')
    args=parser.parse_args();run(args.candidate.resolve(),[p.resolve() for p in args.loop],[p.resolve() for p in args.lower_gain_control],args.output.resolve())
