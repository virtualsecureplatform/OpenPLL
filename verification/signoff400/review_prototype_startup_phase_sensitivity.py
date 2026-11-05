"""Check added startup-phase observations without promoting model qualification."""
import argparse
import csv
import json
from pathlib import Path
from common_v3 import PROFILE,save,sha,verify
from review_prototype_common_gain_diagnostic_v3 import window_pass


def first_edge(directory):
    with (directory/'cold_start_phase0/controls.csv').open() as stream:
        for row in csv.DictReader(stream):
            if row['event']=='EDGE':return int(row['time_ps'])
    raise ValueError('first oscillator edge absent')


def run(baselines,shifted,output):
    profile=json.loads(PROFILE.read_text())
    pins={str(p):sha(p) for p in (PROFILE,Path(__file__).resolve(),
        Path(__file__).with_name('review_prototype_common_gain_diagnostic_v3.py'))}
    def read(directory):
        receipt=directory/'assessment.json';a=json.loads(receipt.read_text())
        verify(a['input_sha256']);verify(a['artifacts'])
        if not a['exact_synthesized_candidate_sources_executed'] or a['profile_sha256']!=sha(PROFILE):
            raise ValueError('exact candidate and profile required')
        pins[str(receipt)]=sha(receipt)
        return a
    base={};sources=None;gain=None
    for directory in baselines:
        a=read(directory);corner=a['corner']
        if corner in base or not a['all_trace_cases_passed'] or len(a['records'])!=12:
            raise ValueError('five distinct complete baseline corners required')
        if sources is None:sources=a['candidate_source_sha256'];gain=(a['ki'],a['kp'])
        if sources!=a['candidate_source_sha256'] or gain!=(a['ki'],a['kp']):
            raise ValueError('common source and gain required')
        base[corner]=(a,directory,first_edge(directory))
    if set(base)!=set(profile['corners']):raise ValueError('all five baseline corners required')
    seen=set();results=[]
    for directory in shifted:
        a=read(directory);corner=a['corner'];hold=a['dco_startup_hold_ps']
        if (corner,hold) in seen or hold not in (625,1250,1875):
            raise ValueError('duplicate or unsupported startup sensitivity point')
        seen.add((corner,hold));b,origin,edge=base[corner]
        if (sources!=a['candidate_source_sha256'] or gain!=(a['ki'],a['kp'])
                or a['dco_fixed_duty_ppm']!=b['dco_fixed_duty_ppm']):
            raise ValueError('source, gain or native duty differs from baseline')
        for suffix in ('/models.json','/dco_table.txt','/detector.v','/parameters.json'):
            left={p:d for p,d in a['input_sha256'].items() if p.endswith(suffix)}
            right={p:d for p,d in b['input_sha256'].items() if p.endswith(suffix)}
            if not left or left!=right:raise ValueError('tuning or detector model differs')
        if first_edge(directory)-edge!=hold:raise ValueError('requested initial phase shift was not observed')
        if len(a['records'])!=3 or {(r['scenario'],r['phase_offset_ns']) for r in a['records']}!={(s,0) for s in profile['scenarios']}:
            raise ValueError('all three recovery scenarios required at each added phase')
        windows=[];acquisition=[]
        for record in a['records']:
            if record['native_exit']!=0 or not record['passed']:raise ValueError('startup sensitivity trace failed')
            expected=1 if record['scenario']=='cold_start' else 2
            if len(record['segments'])!=expected:raise ValueError('recovery segment missing')
            for segment in record['segments']:
                path=directory/f'{record["scenario"]}_phase0'/f'segment{segment["segment"]}.json'
                if a['artifacts'].get(str(path))!=sha(path):raise ValueError('segment artifact identity differs')
                data=json.loads(path.read_text());final=data['windows'][-profile['sustained_windows']:]
                delay=data['acquisition_confirmed_ns']-data['stimulus_ns']
                if (not data['complete_control_trace_checked'] or not data['sustained_final_pass']
                        or len(final)!=4 or not all(window_pass(w,profile) for w in final)
                        or not 0<=delay<=profile['acquisition_limit_ns']):
                    raise ValueError('direct final-window or acquisition criterion failed')
                windows.extend(final);acquisition.append(delay)
        results.append(dict(corner=corner,startup_hold_ps=hold,observed_first_edge_shift_ps=hold,
            cases=3,segments=len(acquisition),final_windows=len(windows),
            maximum_acquisition_ns=max(acquisition),
            maximum_phase_span_ns=max(w['phase_span_ns'] for w in windows),
            maximum_absolute_phase_drift_ns=max(abs(w['phase_drift_ns']) for w in windows)))
    if seen!={(c,h) for c in profile['corners'] for h in (625,1250,1875)}:
        raise ValueError('complete five-corner startup sensitivity matrix required')
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    detail=output/'points.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        candidate_source_sha256=sources,ki=gain[0],kp=gain[1],
        additional_cases=45,additional_recovery_segments=75,independently_checked_added_final_windows=300,
        requested_initial_edge_displacements_verified=True,all_added_diagnostic_trace_criteria_pass=True,
        startup_phase_samples_ps=[0,625,1250,1875],continuous_phase_coverage_claimed=False,
        actual_loaded_native_startup_model_included=False,physical_models_qualified=False,
        closed_loop_operation_qualified=False,release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','shifted'):parser.add_argument('--'+name,type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run([p.resolve() for p in args.baseline],[p.resolve() for p in args.shifted],args.output.resolve())
