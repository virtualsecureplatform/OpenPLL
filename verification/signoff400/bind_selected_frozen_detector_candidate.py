"""Bind an independently checked candidate without refitting or qualification."""
import argparse,json,os,shutil
from pathlib import Path
from common_v3 import save,sha,verify
from follow_selected_frozen_corner_candidate import prelaunch
from fit_selected_corner_detector import observe_corner
from fit_selected_detector_diagnostic import same_model


PASS_FIELDS=['all_sampled_signs_match','all_event_counts_match','all_edges_within_observed_fit_band']


def bind(prior,comparison,protocol_path,fresh_path,output):
    if output.exists():raise FileExistsError(output)
    p,t,protocol,fresh=[json.loads(x.read_text()) for x in [prior,comparison,protocol_path,fresh_path]]
    for a in [p,t,protocol,fresh]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    if not all(t.get(k) is True and fresh.get(k) is True for k in PASS_FIELDS):
        raise ValueError('complete passing comparison and fresh sign/count/timing checks required')
    if fresh.get('parameters_refitted') is not False or fresh.get('predeclared_fresh_independent_holdout') is not True:
        raise ValueError('explicit independent frozen validation required')
    if protocol['input_sha256'].get(str(comparison))!=sha(comparison):
        raise ValueError('comparison must be frozen in the prelaunch protocol')
    if fresh['input_sha256'].get(str(protocol_path))!=sha(protocol_path):
        raise ValueError('fresh replay must bind identical prelaunch protocol')
    case=Path(protocol['case']);native_owner=case/'native/owner.json'
    prelaunch(protocol,json.loads(native_owner.read_text()),os.sysconf('SC_CLK_TCK'))
    assessment=case/'waveform_assessment/assessment.json'
    if fresh['record']['assessment']!=str(assessment) or any(r['assessment']==str(assessment) for r in t['records']):
        raise ValueError('fresh case must be distinct from every comparison case')
    paths=[Path(x) for x in protocol['input_sha256']]
    models=[x for x in paths if x.name=='detector.v'];parameters=[x for x in paths if x.name=='parameters.json']
    if len(models)!=1 or len(parameters)!=1 or models[0].parent!=parameters[0].parent:
        raise ValueError('unique frozen candidate model and parameters required')
    model,params_path=models[0],parameters[0]
    if any(t['input_sha256'].get(str(x))!=sha(x) or fresh['input_sha256'].get(str(x))!=sha(x) for x in [model,params_path]):
        raise ValueError('same candidate bytes required throughout comparison and validation')
    params=json.loads(params_path.read_text());prior_parameters=prior.parent/'parameters.json';old=json.loads(prior_parameters.read_text())
    if p['artifacts'].get(str(prior_parameters))!=sha(prior_parameters):
        raise ValueError('prior receipt must bind unchanged original parameters')
    op=p.get('operating_point',dict(corner=p.get('corner'),temperature_c=27,supply_v=1.8))
    if params.get('operating_point')!=op or protocol['corner']!=op['corner']:
        raise ValueError('same prior, candidate and validation operating point required')
    if params['native_clock_latency_ns']!=old['native_clock_latency_ns'] or params['observed_transition_bracket_ps']!=old['observed_transition_bracket_ps']:
        raise ValueError('original latency parameters and training bracket must stay unchanged')
    lo,hi=old['observed_transition_bracket_ps']
    if not lo < -params['lookback_ps'] < hi:raise ValueError('strictly interior prior-bracket candidate required')
    observations=[observe_corner(Path(r['assessment']),op['corner']) for r in t['records']]
    observations.append(observe_corner(assessment,op['corner']))
    if same_model(observations)!=p['native_model_sha256']:
        raise ValueError('same physical native model required for all evidence')
    records=[dict(scope='candidate_comparison',**r) for r in t['records']]
    records.append(dict(scope='fresh_independent_holdout',**fresh['record']))
    files=[prior,prior_parameters,comparison,protocol_path,fresh_path,model,params_path,native_owner,Path(__file__).resolve()]
    files += [Path(r['assessment']) for r in records]
    files += [x for o in observations for x in o['binding_paths']]
    files += [Path(__file__).with_name(n) for n in ['common_v3.py','follow_selected_frozen_corner_candidate.py','fit_selected_corner_detector.py','fit_selected_detector_diagnostic.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py']]
    pins={str(x):sha(x) for x in files};verify(pins);output.mkdir(parents=True)
    shutil.copyfile(model,output/'detector.v');shutil.copyfile(params_path,output/'parameters.json')
    if sha(output/'detector.v')!=sha(model) or sha(output/'parameters.json')!=sha(params_path):
        raise ValueError('candidate copy must be byte identical')
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/name):sha(output/name) for name in ['detector.v','parameters.json']},
        operating_point=op,native_model_sha256=p['native_model_sha256'],records=records,
        **{k:True for k in PASS_FIELDS},parameters_refitted=False,candidate_bytes_unchanged_since_prelaunch=True,
        comparison_cases_used_for_candidate_selection=True,fresh_independent_holdout_cases=1,
        diagnostic=True,synthetic=True,status='independently_checked_diagnostic_candidate',
        corner_sender_waveforms_correlated=False,full_phase_coverage_qualified=False,independent_qualification_holdouts_complete=False,
        native_interface_qualified=False,complete_controller_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prior','comparison','protocol','fresh','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();bind(a.prior.resolve(),a.comparison.resolve(),a.protocol.resolve(),a.fresh.resolve(),a.output.resolve())
