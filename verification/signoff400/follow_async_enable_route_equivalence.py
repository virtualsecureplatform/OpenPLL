"""Prove the separate candidate's routed logic after its original route ends.

Run inside the release image. No layout promotion or native retry is performed.
"""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute


def run(route, mapping, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {27})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        worker = json.loads((route/'route.process.json').read_text())
        checker = ROOT/'verification/prototype400/check_route_equivalence_v2.py'
        source = mapping/'assessment.json'
        mapped = json.loads(source.read_text())
        verify(mapped['input_sha256'])
        verify(mapped['artifacts'])
        paths = [Path(__file__).resolve(), source, mapping/'mapped.json', checker,
                 ROOT/'build/apptainer/openpll-release-modern.sif', route/'route.process.json',
                 *(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py'))]
        pins = {str(p): sha(p) for p in paths}
        save(output/'inputs.json', dict(input_sha256=pins, route=str(route), mapping=str(mapping),
            candidate_layout_promoted=False, native_cases_launched=0))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        while True:
            state = json.loads((route/'status.json').read_text())['state']
            if state == 'digital_route_completed_pending_independent_checks':
                break
            if state == 'physical_build_nonpass' or identity(worker['pid']) != worker['birth']:
                raise ValueError('original route stopped without complete routed assessment')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('route observation deadline; original job unchanged')
            save(output/'status.json', dict(state='waiting_for_original_candidate_route', release_ready=False))
            time.sleep(10)
        receipt = route/'assessment.json'
        routed = json.loads(receipt.read_text())
        verify(routed['input_sha256'])
        verify(routed['artifacts'])
        if routed['candidate_source_sha256'] != mapped['candidate_source_sha256']:
            raise ValueError('route and golden mapping must bind the same candidate source')
        verify(pins)
        pins[str(receipt)] = sha(receipt)
        limit = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        save(output/'status.json', dict(state='proving_candidate_routed_logic', release_ready=False))
        with lease(1, 4, limit):
            execute(['/usr/bin/python3', checker, '--route', route, '--gold-json', mapping/'mapped.json',
                     '--output', output/'proof'], output/'proof.log', limit, 4)
        proof = output/'proof/assessment.json'
        result = json.loads(proof.read_text())
        verify(result['input_sha256'])
        verify(result['artifacts'])
        if not (result['all_transition_and_output_functions_equivalent']
                and result['corrupted_reset_function_rejected']):
            raise ValueError('routed state/clock/reset equivalence and rejecting control required')
        verify(pins)
        save(output/'assessment.json', dict(input_sha256=pins,
            artifacts={str(proof): sha(proof)}, matched_state_primitives=result['matched_state_primitives'],
            all_transition_and_output_functions_equivalent=True, corrupted_reset_function_rejected=True,
            candidate_layout_promoted=False, physical_CDC_qualified=False,
            physical_timing_qualified=False, native_models_transferred=False, release_ready=False))
        save(output/'status.json', dict(state='candidate_routed_logic_proved', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error),
            original_route_unchanged=True, release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('route','mapping','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.route.resolve(), args.mapping.resolve(), args.output.resolve())
