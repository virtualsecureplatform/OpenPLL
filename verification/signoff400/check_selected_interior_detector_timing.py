"""Check a diagnostic interior variant without claiming fresh holdout validation."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from fit_selected_corner_detector import observe_corner
from fit_selected_detector_diagnostic import replay,same_model


def run(selection,name,output):
    if output.exists():raise FileExistsError(output)
    a=json.loads(selection.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if name not in a['common_fixed_sign_count_models']:
        raise ValueError('previously replayed common sign/count candidate required')
    matches=[r for r in a['models'] if r['name']==name]
    if len(matches)!=1:raise ValueError('unique pinned candidate required')
    model=Path(matches[0]['model']);parameters=model.parent/'parameters.json'
    for p in [model,parameters]:
        if a['artifacts'].get(str(p))!=sha(p):raise ValueError('candidate bytes changed')
    params=json.loads(parameters.read_text());corner=params['operating_point']['corner']
    originals=[Path(p) for p in a['input_sha256'] if p.endswith('/parameters.json')]
    if len(originals)!=1:raise ValueError('unique prior training parameters required')
    prior=json.loads(originals[0].read_text())
    if params['native_clock_latency_ns']!=prior['native_clock_latency_ns']:
        raise ValueError('unchanged prior nominal latency parameters required')
    paths=[Path(r['case']) for r in a['per_case_admission']]
    observations=[observe_corner(p,corner) for p in paths];same_model(observations)
    sources=[selection,model,parameters,*paths,Path(__file__).resolve(),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    sources += [Path(__file__).with_name(n) for n in ['common_v3.py','fit_selected_corner_detector.py','fit_selected_detector_diagnostic.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py']]
    sources += [p for o in observations for p in o['binding_paths']]
    pins={str(p):sha(p) for p in sources};output.mkdir(parents=True)
    records=[replay(o,params,model,output/f'case_{i}') for i,o in enumerate(observations)]
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
        operating_point=params['operating_point'],candidate=name,records=records,
        all_sampled_signs_match=all(r['all_sampled_signs_match'] for r in records),
        all_event_counts_match=all(r['all_event_counts_match'] for r in records),
        all_edges_within_observed_fit_band=all(r['all_edges_within_observed_fit_band'] for r in records),
        parameters_modified=False,prior_nominal_latencies_unchanged=True,
        observations_previously_used_for_candidate_comparison=True,fresh_independent_validation_complete=False,
        corner_sender_waveforms_correlated=False,closed_loop_stress_executed=False,native_interface_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection',type=Path,required=True);p.add_argument('--candidate',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.selection.resolve(),a.candidate,a.output.resolve())
