"""Check the isolated clock ECO in a fresh layout bundle, without selection."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute


def completed(path):
    value = json.loads(path.read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'])
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1',
                      OPENBLAS_NUM_THREADS='1', GOMAXPROCS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    route = base / 'selected_keeper_clock_branch_candidate_1452'
    logic = base / 'selected_keeper_clock_branch_logic_1455'
    proof = base / 'selected_keeper_clock_branch_equivalence_1456'
    try:
        rr, lr, pr = [completed(p / 'assessment.json') for p in (route, logic, proof)]
        if not (rr.get('native_candidate_route_completed') is True
                and lr.get('digital_routing_completed') is True
                and pr.get('all_transition_and_output_functions_equivalent') is True
                and pr.get('corrupted_reset_function_rejected') is True):
            raise ValueError('completed route and positive/negative Boolean controls required')
        if (lr['source_candidate_receipt'] != str(route / 'assessment.json')
                or lr['input_sha256'].get(str(route / 'assessment.json')) != sha(route / 'assessment.json')
                or lr['input_sha256'].get(str(route / 'route.odb')) != rr['artifacts'][str(route / 'route.odb')]
                or pr['input_sha256'].get(str(logic / 'assessment.json')) != sha(logic / 'assessment.json')
                or pr['input_sha256'].get(str(logic / 'route.v')) != lr['artifacts'][str(logic / 'route.v')]):
            raise ValueError('equivalence must bind this exact physical database through its exported netlist')
        checker = ROOT / 'verification/prototype400/check_layout.py'
        files = [Path(__file__).resolve(), checker, *[p / 'assessment.json' for p in (route, logic, proof)],
                 ROOT / 'verification/timing400/check_compact_clock_tree.py',
                 *[ROOT / 'verification/timing450' / n for n in ('signoff.py', 'run.py', 'hs_views.py')],
                 *[Path(__file__).with_name(n) for n in ('common_v3.py', 'resources.py', 'compiled_charge_v2.py')]]
        pins = {str(p): sha(p) for p in files}
        bundle = output / 'candidate'
        bundle.mkdir()
        artifacts = {}
        for name in ('route.odb', 'route.def', 'route.nom.spef'):
            source = route / name
            if rr['artifacts'].get(str(source)) != sha(source):
                raise ValueError('route artifact missing from completed extraction receipt')
            (bundle / name).symlink_to(source)
            artifacts[str(bundle / name)] = sha(source)
        # Compatibility receipt for the unchanged historical checker. It is a new
        # view of verified artifacts, never a modification of the frozen candidate.
        save(bundle / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             digital_routing_completed=True, nominal_rc_extracted=True,
             selected=False, release_ready=False))
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=8,
             native_wall_limit_s=3600, resource_queue_limit_s=86400,
             candidate_selected=False, original_candidate_modified=False))
        save(output / 'status.json', dict(state='waiting_for_layout_check_resources', release_ready=False))
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            save(output / 'status.json', dict(state='checking_streamed_candidate_layout', release_ready=False))
            execute([sys.executable, checker, '--route', bundle], output / 'native.log', deadline, 8)
        completion = bundle / 'layout_audit_runner/completion.json'
        c = json.loads(completion.read_text())
        verify(c['input_sha256'])
        result_path = bundle / 'signoff/assessment.json'
        result = json.loads(result_path.read_text())
        verify(result['sha256'])
        if c['audit_sha256'] != sha(result_path):
            raise ValueError('native completion does not bind layout assessment')
        verify(pins)
        keys = ('power_pins_total', 'power_pins_connected', 'antenna_net_violations',
                'antenna_pin_violations', 'magic_drc_rectangles', 'lvs_unique_match', 'diagnostic_physical_pass')
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in (completion, result_path, output / 'native.log')},
             digital_component_results={k: result[k] for k in keys},
             original_candidate_modified=False, candidate_selected=False,
             assembled_parent_checked=False, physical_timing_qualified=False,
             physical_CDC_qualified=False, density_EM_IR_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='candidate_layout_checks_assessed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
