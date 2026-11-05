"""Consolidate finite numerical observations without asserting a domain enclosure."""
import argparse
import json
from pathlib import Path
from common import save,sha


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    baseline=base/'startup_timing_mux2_4_15PVT_raw_001/assessment.json';requirements=Path('verification/signoff400/requirements.json').resolve()
    campaign_paths={key:base/f'startup_timing_mux2_4_{key}_control_001/assessment.json' for key in ('step','reltol','abstol')}
    paths=[baseline,requirements,*campaign_paths.values(),Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    b=json.loads(baseline.read_text());spec=json.loads(requirements.read_text());expected={(c,t,1.8) for c in spec['corners'] for t in spec['temperatures_c']}
    baseline_cases={r['label']:r for r in b['case_results']};envelope={};summary={}
    if len(baseline_cases)!=15 or not b['all_raw_fixture_events_pass']:raise ValueError('complete unique passing baseline required')
    for control,parent in campaign_paths.items():
        a=json.loads(parent.read_text());terminal='all_15_independent_timestep_controls_terminal' if control=='step' else 'all_15_independent_tolerance_controls_terminal'
        if not a[terminal] or a['input_sha256'][str(baseline)]!=pins[str(baseline)]:raise ValueError('complete same-baseline control required')
        points=set();max_delta=0;changes=unmatched=compared=0
        for case in a['case_results']:
            label=case['label'];prior=Path(baseline_cases[label]['assessment']);current=Path(case['assessment']);comparison=Path(case['comparison'])
            for path,digest in ((prior,baseline_cases[label]['assessment_sha256']),(current,case['assessment_sha256']),(comparison,case['comparison_sha256'])):
                pins[str(path)]=sha(path)
                if pins[str(path)]!=digest:raise ValueError('native observation or comparison changed')
            before,after,delta=[json.loads(p.read_text()) for p in (prior,current,comparison)]
            if before['pvt']!=after['pvt'] or before['fixtures']!=54 or after['fixtures']!=54 or not after['compiled_streaming_assessor_used']:raise ValueError('matching complete compiled native observations')
            pvt=after['pvt'];point=(pvt['corner'],pvt['temperature_c'],pvt['supply_v'])
            if point in points:raise ValueError('duplicate PVT control point')
            points.add(point)
            for left,right,record in zip(before['records'],after['records'],delta['records'],strict=True):
                index=left['case_index']
                if right['case_index']!=index or record['case_index']!=index:raise ValueError('matching native fixture index required')
                changed=any(left[k]!=right[k] for k in ('passed','strict_output_slew_passed'));changes+=changed;missing=[];observations={}
                for field in ('input_rise_delay_ns','input_fall_delay_ns','output_rise_slew_ns','output_fall_slew_ns'):
                    x,y=left.get(field),right.get(field)
                    if x is None or y is None or len(x)!=len(y):missing.append(field);continue
                    values=[v-u for u,v in zip(x,y)];observations[field]=values;max_delta=max([max_delta,*map(abs,values)])
                if observations!=record['signed_control_minus_baseline_ns'] or missing!=record['unmatched_metrics']:raise ValueError('independent signed metric comparison differs')
                unmatched+=bool(missing);compared+=1;key=(label,index)
                if key not in envelope:envelope[key]=dict(PVT=pvt,case_index=index,baseline_record=left,observed_control_deltas_ns={})
                envelope[key]['observed_control_deltas_ns'][control]=observations
        if points!=expected or compared!=810:raise ValueError('full required PVT and fixture scope')
        if changes!=a['changed_fixture_outcomes'] or unmatched!=a['fixtures_with_unmatched_metrics'] or max_delta!=a['maximum_absolute_matched_metric_difference_ns']:raise ValueError('parent aggregate mismatch')
        summary[control]=dict(PVT_points=len(points),fixtures=compared,changed_outcomes=changes,unmatched_metric_fixtures=unmatched,observed_maximum_absolute_metric_delta_ns=max_delta)
    target=output/'observed_control_deltas.jsonl'
    with target.open('x') as stream:
        for key in sorted(envelope):
            row=envelope[key]
            if set(row['observed_control_deltas_ns'])!=set(campaign_paths):raise ValueError('complete per-fixture numerical controls')
            stream.write(json.dumps(row)+'\n')
    if any(sha(Path(p))!=digest for p,digest in pins.items()):raise ValueError('source changed during numerical review')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target)},controls=summary,
         all_15_PVT_and_810_fixtures_per_control_independently_reconciled=True,
         total_control_fixture_comparisons=2430,all_outcomes_unchanged=not any(r['changed_outcomes'] for r in summary.values()),
         all_metrics_matched=not any(r['unmatched_metric_fixtures'] for r in summary.values()),
         measured_differences_are_not_error_enclosures=True,numerical_uncertainty_acceptance_threshold_selected=False,
         numerical_domain_enclosure_qualified=False,interpolation_qualified=False,sequential_constraints_qualified=False,
         physical_timing_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
