"""Generate finite detector stress choices from a frozen measured fit.

Threshold and four latency endpoints give 32 deterministic models. This is not
a uniform uncertainty proof, nor a claim that independent extrema coexist in
silicon. Native replay admission is assessed per case without fitting to it.
"""
import argparse
import copy
import itertools
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from fit_prototype_detector_model import render
from fit_selected_corner_detector import observe_corner
from fit_selected_detector_diagnostic import replay, same_model


def variants(parameters):
    low, high = parameters['observed_transition_bracket_ps']
    if not all(math.isfinite(v) for v in (low, high)) or not low < high < 0:
        raise ValueError('finite ordered negative measured bracket required')
    fields = [('DN','rise'), ('DN','fall'), ('UP','rise'), ('UP','fall')]
    for threshold_index, threshold in enumerate((low, high)):
        for choices in itertools.product((0, 1), repeat=4):
            p = copy.deepcopy(parameters)
            p['lookback_ps'] = -threshold
            for (role, edge), index in zip(fields, choices):
                bounds = p['native_clock_latency_ns'][role][edge]['observed_interval']
                if not all(math.isfinite(v) for v in bounds) or not 0 < bounds[0] <= bounds[1]:
                    raise ValueError('finite positive ordered measured latency intervals required')
                p['native_clock_latency_ns'][role][edge]['nominal'] = bounds[index]
            yield f'phase{threshold_index}_latency'+''.join(map(str,choices)), p, dict(
                threshold_ps=threshold, latency_endpoint_indices=dict(
                    (role+'_'+edge, index) for (role,edge),index in zip(fields,choices)))


def run(prior, bracket_review, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {26})
    a, review = [json.loads(p.read_text()) for p in (prior, bracket_review)]
    for receipt in (a, review):
        verify(receipt['input_sha256'])
        if 'artifacts' in receipt:
            verify(receipt['artifacts'])
    parameters_path = prior.parent/'parameters.json'
    if (review['input_sha256'].get(str(prior)) != sha(prior)
            or review['input_sha256'].get(str(parameters_path)) != sha(parameters_path)
            or review['new_case_used_for_fitting'] is not False
            or review['nominal_parameters_and_Verilog_unchanged'] is not True):
        raise ValueError('review must bind unchanged prior fit and excluded new holdout')
    parameters = json.loads(parameters_path.read_text())
    corner = parameters['operating_point']['corner']
    if review['prior_transition_bracket_ps'] != parameters['observed_transition_bracket_ps']:
        raise ValueError('only prior training bracket may determine stress choices')
    candidates = [Path(r['assessment']) for r in a['records']]
    new_cases = [Path(p) for p in review['input_sha256']
                 if p.endswith('/waveform_assessment/assessment.json')]
    if len(new_cases) != 1 or new_cases[0] in candidates:
        raise ValueError('exactly one separately excluded new native holdout required')
    candidates += new_cases
    observations = [observe_corner(p, corner) for p in candidates]
    if same_model(observations) != a['native_model_sha256']:
        raise ValueError('same native detector model required')
    paths = [prior, bracket_review, parameters_path, Path(__file__).resolve(), *candidates,
             ROOT/'build/apptainer/openpll-release-modern.sif', Path('/usr/bin/iverilog'), Path('/usr/bin/vvp'),
             *(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py',
               'fit_prototype_detector_model.py','fit_selected_corner_detector.py',
               'fit_selected_detector_diagnostic.py','selected_spice_device_conditions.py',
               'audit_selected_dco_history_inputs.py'))]
    paths += [p for o in observations for p in o['binding_paths']]
    pins = {str(p): sha(p) for p in paths}
    save(output/'inputs.json', dict(input_sha256=pins, parameter_selection_uses_new_holdout=False))
    records = []
    with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME)+1800):
        for name, p, selection in variants(parameters):
            folder = output/name
            folder.mkdir()
            model = folder/'detector.v'
            model.write_text(render(p))
            save(folder/'parameters.json', p)
            cases = []
            for index, observation in enumerate(observations):
                result = replay(observation, p, model, folder/f'replay_{index}')
                # The old replay's edge-error limit assumes midpoint latencies.
                # It is deliberately not used to validate endpoint timing.
                cases.append(dict(assessment=result['assessment'],
                    all_sampled_signs_match=result['all_sampled_signs_match'],
                    all_event_counts_match=result['all_event_counts_match']))
            records.append(dict(name=name, model=str(model), model_sha256=sha(model),
                selection=selection, cases=cases))
    admission = []
    for case in candidates:
        matches = [r['name'] for r in records for c in r['cases'] if c['assessment'] == str(case)
                   and c['all_sampled_signs_match'] and c['all_event_counts_match']]
        admission.append(dict(case=str(case), matching_fixed_endpoint_models=matches,
            at_least_one_fixed_model_matches_case_signs_and_counts=bool(matches)))
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in output.rglob('*') if p.is_file()},
        operating_point=parameters['operating_point'], models=records,
        finite_fixed_endpoint_models=len(records), native_replay_cases=len(candidates),
        per_case_admission=admission,
        all_cases_have_a_fixed_sign_count_replay=all(r['at_least_one_fixed_model_matches_case_signs_and_counts'] for r in admission),
        new_holdout_used_for_parameter_selection=False, nominal_fit_modified=False,
        endpoint_timing_qualified=False, cross_cycle_adaptive_ambiguity_covered=False,
        extrema_joint_physical_realizability_claimed=False, closed_loop_stress_executed=False,
        corner_sender_waveforms_correlated=False, uniform_uncertainty_bound_qualified=False,
        native_interface_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prior','bracket-review','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.prior.resolve(), args.bracket_review.resolve(), args.output.resolve())
