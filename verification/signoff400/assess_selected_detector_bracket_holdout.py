"""Distinguish a frozen nominal detector miss from its prior phase ambiguity band.

Does not fit to the holdout or qualify a uniform detector uncertainty envelope.
"""
import argparse,json,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from fit_selected_corner_detector import observe_corner
from fit_selected_detector_diagnostic import same_model


def run(prior,holdout,replay,output):
    output.mkdir(parents=True,exist_ok=False);p,n=[json.loads(x.read_text()) for x in (prior,replay)]
    for a in(p,n):verify(a['input_sha256']);verify(a['artifacts'])
    parameters=prior.parent/'parameters.json';new_parameters=replay.parent/'parameters.json';model=prior.parent/'detector.v';new_model=replay.parent/'detector.v'
    if sha(parameters)!=sha(new_parameters) or sha(model)!=sha(new_model):raise ValueError('nominal model and training parameters must remain frozen')
    fitting=lambda a:{r['assessment'] for r in a['records'] if r['scope']=='fit'}
    if len(fitting(p))!=4 or fitting(p)!=fitting(n):raise ValueError('unchanged four-case fitting set required')
    if str(holdout) in {r['assessment'] for r in p['records']}:raise ValueError('new case must remain independent of the original fit/validation')
    records=[r for r in n['records'] if r['scope']=='holdout' and r['assessment']==str(holdout)]
    if len(records)!=1:raise ValueError('exactly one frozen-model holdout replay required')
    nominal=records[0];params=json.loads(parameters.read_text());corner=params['operating_point']['corner'];observed=observe_corner(holdout,corner)
    if observed['native_model_sha256']!=p['native_model_sha256'] or observed['normal_full_window_completed'] is not True:raise ValueError('same physical model and complete native observation required')
    low,high=params['observed_transition_bracket_ps']
    if not all(math.isfinite(x) for x in (low,high)) or not low<high<0:raise ValueError('prior ordered negative transition bracket required')
    cycles=[]
    for c in observed['cycles']:
        phase=c['phase_ps'];inside=low<=phase<=high;outside_expected='dn' if phase<low else 'up' if phase>high else None
        cycles.append(dict(**c,inside_prior_transition_bracket=inside,outside_bracket_expected=outside_expected,nominal_prediction='dn' if phase < -params['lookback_ps'] else 'up',admitted_by_prior_bracket=inside or c['decision']==outside_expected))
    latency=[]
    for role,edges in observed['latencies'].items():
        for edge,values in edges.items():
            bounds=params['native_clock_latency_ns'][role][edge]['observed_interval'];nom=params['native_clock_latency_ns'][role][edge]['nominal'];quant=.00101
            latency.append(dict(role=role,edge=edge,observed_events=len(values),observed_latencies_ns=values,prior_interval_ns=bounds,quantization_allowance_ns=quant,all_observed_latencies_in_prior_band=all(bounds[0]-quant<=v<=bounds[1]+quant for v in values) if values else None,errors_from_prior_nominal_ps=[(v-nom)*1000 for v in values]))
    posterior_low=max([low]+[c['phase_ps'] for c in cycles if c['decision']=='dn']);posterior_high=min([high]+[c['phase_ps'] for c in cycles if c['decision']=='up'])
    outside=[c for c in cycles if not c['inside_prior_transition_bracket']]
    paths=[prior,holdout,replay,parameters,new_parameters,model,new_model,*observed['binding_paths'],ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).resolve(),*(Path(__file__).with_name(name) for name in ('common_v3.py','fit_selected_corner_detector.py','fit_selected_detector_diagnostic.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py'))];pins={str(q):sha(q) for q in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,operating_point=params['operating_point'],normal_native_completion=True,frozen_training_set_cases=4,new_case_used_for_fitting=False,nominal_parameters_and_Verilog_unchanged=True,prior_transition_bracket_ps=[low,high],cycles=cycles,nominal_sampled_signs_match=nominal['all_sampled_signs_match'],nominal_event_counts_match=nominal['all_event_counts_match'],nominal_edge_pairing_valid=nominal['all_event_counts_match'],all_observed_decisions_admitted_by_prior_bracket=all(c['admitted_by_prior_bracket'] for c in cycles),outside_prior_bracket_cycles=len(outside),outside_bracket_sign_check=all(c['decision']==c['outside_bracket_expected'] for c in outside) if outside else None,conditional_native_event_latencies=latency,all_observed_conditional_latencies_within_prior_band=all(r['all_observed_latencies_in_prior_band'] for r in latency if r['observed_events']),observed_event_classes=sum(bool(r['observed_events']) for r in latency),posterior_transition_bracket_if_recalibrated_ps=[posterior_low,posterior_high],posterior_bracket_applied_to_current_model=False,scope='One new FF near-transition holdout under recorded TT excitation. Phase-band admission does not turn a wrong nominal decision or unmatched event counts into nominal validation. Conditional event timing uses each native edge causal reference, not zip pairing across different cycles.',corner_sender_waveforms_correlated=False,full_phase_coverage_qualified=False,uniform_uncertainty_bound_qualified=False,native_interface_qualified=False,diagnostic=True,release_ready=False));save(output/'status.json',dict(state='frozen_bracket_holdout_assessed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prior','holdout','replay','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.prior.resolve(),a.holdout.resolve(),a.replay.resolve(),a.output.resolve())
