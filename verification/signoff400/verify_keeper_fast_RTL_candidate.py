"""Verify completed TT candidate receipts and retained final-window acceptance metrics."""
import json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,spec
from resources import lease


def run():
    base=ROOT/'build/signoff400';campaign=base/'selected_keeper_fast_RTL_gain_screen_1553'
    output=base/'selected_keeper_fast_RTL_candidate_review_1555';output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{30})
    receipt=campaign/'assessment.json';record=json.loads(receipt.read_text())
    verify(record['input_sha256']);verify(record['artifacts'])
    if record['TT_diagnostic_candidate']!=[1,2] or record['release_gain_selected'] is not False:
        raise ValueError('expected diagnostic-only candidate required')
    gains={(r['ki'],r['kp']):r['state'] for r in record['gains']}
    if any(gains.get(pair)!='diagnostic_failure' for pair in [(1,0),(1,1)]):
        raise ValueError('every lower gain must be resolved as a diagnostic failure')
    progress=campaign/'progress.json';cases=json.loads(progress.read_text())['cases']
    selected=[c for c in cases if (c['ki'],c['kp'])==(1,2)]
    profile=spec();names=profile['scenarios'];phases=profile['reference_phase_offsets_ns']
    expected={(name,phase) for name in names for phase in phases}
    if len(selected)!=12 or {(c['scenario'],c['phase_ns']) for c in selected}!=expected:
        raise ValueError('exactly all12 distinct TT cases required')
    files=[receipt,progress,Path(__file__).resolve()];windows=[];segments=0;confirmations=[]
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for case in selected:
            path=Path(case['receipt']);a=json.loads(path.read_text())
            verify(a['input_sha256']);verify(a['artifacts'])
            if a['native_exit']!=0 or not all(a[k] is True for k in ('terminal_marker_present','functional_trace_pass','reference_phase_coverage_pass')):
                raise ValueError('completed actual-RTL functional trace and phase coverage required')
            arguments=json.loads(path.with_name('inputs.json').read_text())['case_arguments']
            expected_arguments=dict(ki=1,kp=2,coarse=23,seed=128,polarity=1,
                scenario=names.index(case['scenario']),phase_ns=case['phase_ns'])
            if arguments!=expected_arguments:raise ValueError('case arguments differ from declared TT matrix')
            files.append(path)
            count=1 if case['scenario']=='cold_start' else 2
            for segment in range(count):
                segment_path=path.with_name(f'segment{segment}_acceptance.json')
                s=json.loads(segment_path.read_text());files.append(segment_path)
                if not s['passed'] or not s['sustained_final_pass']:raise ValueError('segment acceptance failed')
                confirmation=s['acquisition_confirmed_ns']-s['stimulus_ns']
                if not 0<=confirmation<=profile['acquisition_limit_ns']:raise ValueError('acquisition deadline failed')
                confirmations.append(confirmation)
                final=s['windows'][-profile['sustained_windows']:]
                if len(final)!=4:raise ValueError('four final windows required')
                for w in final:
                    limits=[('frequency_error_ppm',profile['frequency_error_ppm']),
                            ('phase_span_ns',2.5*profile['phase_span_output_periods']),
                            ('phase_mean_ns',2.5*profile['phase_mean_output_periods']),
                            ('phase_drift_ns',2.5*profile['phase_drift_output_periods'])]
                    if (not w['passed'] or w['cycle_slip'] or w['fine_outside_operating_range']
                            or any(not math.isfinite(w[k]) or abs(w[k])>limit for k,limit in limits)):
                        raise ValueError('explicit final-window limits failed')
                    if not profile['fine_code_min']<=w['fine_min']<=w['fine_max']<=profile['fine_code_max']:
                        raise ValueError('fine code range failed')
                    windows.append(w)
                segments+=1
    metrics={k:max(abs(w[k]) for w in windows) for k in
             ('frequency_error_ppm','phase_span_ns','phase_mean_ns','phase_drift_ns')}
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
         TT_diagnostic_candidate=[1,2],cases_verified=12,segments_verified=segments,final_windows_verified=len(windows),
         worst_final_metrics=metrics,maximum_acquisition_confirmation_ns=max(confirmations),
         final_fine_min=min(w['fine_min'] for w in windows),final_fine_max=max(w['fine_max'] for w in windows),
         exact_case_arguments_verified=True,all_receipt_inputs_and_artifacts_verified=True,
         other_corners_verified=False,frequency_interpolation_error_bound_qualified=False,
         detector_and_clock_models_qualified=False,physical_PLL_lock_qualified=False,release_ready=False))


if __name__=='__main__':run()
