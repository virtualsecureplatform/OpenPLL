"""Wait for multiple raw probes and fit only after measured phase bracketing.

No native cases or retries are launched. Holdout observations never determine
the training bracket or parameters. Run inside the pinned release container.
"""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from fit_selected_corner_detector import observe_corner, run as fit_corner
from fit_selected_detector_diagnostic import same_model


def negative_bracket(observations):
    cycles = [cycle for observation in observations for cycle in observation['cycles']]
    dn = [c['phase_ps'] for c in cycles if c['decision'] == 'dn']
    up = [c['phase_ps'] for c in cycles if c['decision'] == 'up']
    if not dn or not up:
        return None
    low, high = max(dn), min(up)
    return [low, high] if low < high < 0 else None


def run(waiting, fitting, holdouts, corner, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {25})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        if (not waiting or len(set(waiting)) != len(waiting)
                or not set(waiting) <= set(fitting)
                or not fitting or not holdouts
                or len(set(fitting+holdouts)) != len(fitting)+len(holdouts)):
            raise ValueError('distinct probes within disjoint nonempty training/holdout sets required')
        owners = {p: json.loads((p/'owner.json').read_text()) for p in waiting}
        folder = Path(__file__).resolve().parent
        paths = [Path(__file__).resolve(), ROOT/'build/apptainer/openpll-release-modern.sif',
                 Path('/usr/bin/iverilog'), Path('/usr/bin/vvp'),
                 *(folder/n for n in ('common_v3.py', 'resources.py', 'fit_selected_corner_detector.py',
                   'fit_selected_detector_diagnostic.py', 'fit_prototype_detector_model.py',
                   'selected_spice_device_conditions.py', 'audit_selected_dco_history_inputs.py'))]
        paths += [p/name for p in waiting for name in ('owner.json','manifest.json','native/manifest.json')]
        paths += [p/'waveform_assessment/assessment.json' for p in fitting+holdouts if p not in waiting]
        pins = {str(p): sha(p) for p in paths}
        verify(pins)
        save(output/'inputs.json', dict(input_sha256=pins, waiting=list(map(str, waiting)),
            fitting=list(map(str, fitting)), holdouts=list(map(str, holdouts)), corner=corner,
            bracket_selected_only_from_training=True, native_cases_launched=0,
            automatic_identical_retry=False, release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+12600
        while True:
            pending = []
            for case, owner in owners.items():
                state = json.loads((case/'status.json').read_text())['state']
                if state == 'corner_detector_response_measured':
                    continue
                if state == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
                    raise ValueError('original probe stopped without normal complete response: '+str(case))
                pending.append(str(case))
            if not pending:
                break
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('observer deadline; original native jobs unchanged')
            save(output/'status.json', dict(state='waiting_for_corner_raw_bracket_probes',
                pending=pending, release_ready=False))
            time.sleep(10)
        verify(pins)
        training_paths = [p/'waveform_assessment/assessment.json' for p in fitting]
        holdout_paths = [p/'waveform_assessment/assessment.json' for p in holdouts]
        observations = [observe_corner(p, corner) for p in training_paths]
        same_model(observations)
        bracket = negative_bracket(observations)
        paths = [*training_paths, *(p for o in observations for p in o['binding_paths'])]
        pins.update({str(p): sha(p) for p in paths})
        guard = output/'bracket_decision.json'
        save(guard, dict(input_sha256=pins, measured_negative_transition_bracket_ps=bracket,
            measured_training_cycles=[dict(assessment=o['assessment'], cycles=o['cycles']) for o in observations],
            holdouts_used_for_bracket=False, fitting_allowed=bracket is not None,
            expected_decision_assumed=False, release_ready=False))
        if bracket is None:
            save(output/'status.json', dict(state='needs_measured_negative_transition_bracket',
                native_cases_launched=0, release_ready=False))
            return
        save(output/'status.json', dict(state='fitting_measured_corner_raw_bracket', release_ready=False))
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME)+600):
            fit_corner(training_paths, holdout_paths, corner, output/'model')
        receipt = output/'model/assessment.json'
        result = json.loads(receipt.read_text())
        verify(result['input_sha256'])
        verify(result['artifacts'])
        verify(pins)
        save(output/'assessment.json', dict(input_sha256=pins,
            artifacts={str(p): sha(p) for p in (guard, receipt)},
            operating_point=result['operating_point'], measured_transition_bracket_ps=bracket,
            fit_assessments=result['fit_assessments'], holdout_assessments=result['holdout_assessments'],
            all_sampled_signs_match=result['all_sampled_signs_match'],
            all_event_counts_match=result['all_event_counts_match'],
            all_edges_within_observed_fit_band=result['all_edges_within_observed_fit_band'],
            native_cases_launched=0, corner_sender_waveforms_correlated=False,
            native_interface_qualified=False, uniform_uncertainty_bound_qualified=False,
            full_phase_coverage_qualified=False, release_ready=False))
        save(output/'status.json', dict(state='corner_raw_bracket_fit_assessed', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error),
            original_native_jobs_unchanged=True, release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('wait', 'fit', 'holdout'):
        parser.add_argument('--'+name, action='append', type=Path, required=True)
    parser.add_argument('--corner', choices=('ff','ss','sf','fs'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run([p.resolve() for p in args.wait], [p.resolve() for p in args.fit],
        [p.resolve() for p in args.holdout], args.corner, args.output.resolve())
