"""Bind retained logic proofs and classify every reset endpoint without a timed path."""
import argparse
from collections import Counter
import json
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from inventory_mapped_CDC import inventory
from compare_mapped_routed_CDC import clock_roots


def checked(path, artifacts_required=True):
    value = json.loads(path.read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'] if artifacts_required else value.get('artifacts', {}))
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    base = ROOT / 'build/signoff400'
    route = base / 'prototype_v3_selected_route_019/assessment.json'
    mapped = base / 'prototype_v3_fixed_divider_candidate_001/compact/mapped.json'
    coverage = base / 'selected_keeper_reset_endpoint_coverage_1496'
    mask = base / 'prototype_v3_integrated_mask_rearm_proof_001/assessment.json'
    seed = base / 'selected_keeper_seed_RTL_binding_1386/assessment.json'
    reuse = base / 'selected_keeper_digital_macro_reuse_1439/assessment.json'
    try:
        r = json.loads(route.read_text())
        verify(r['candidate_source_sha256'])
        c, p, s = [checked(path) for path in (coverage / 'assessment.json', mask, seed)]
        g = checked(reuse, artifacts_required=False)
        equivalence = base / 'prototype_v3_selected_equivalence_019/assessment.json'
        e = checked(equivalence)
        route_v = route.parent / 'route.v'
        if (e['input_sha256'].get(str(mapped)) != sha(mapped)
                or e['input_sha256'].get(str(route_v)) != r['artifacts'].get(str(route_v))
                or not e['all_transition_and_output_functions_equivalent']
                or not e['corrupted_reset_function_rejected']):
            raise ValueError('mapped inventory must bind the completed routed-equivalence controls')
        sources = {name: digest for name, digest in r['candidate_source_sha256'].items() if name.endswith('.v')}
        if len(sources) != 9 or any(p['input_sha256'].get(name) != digest
                                   or s['input_sha256'].get(name) != digest for name, digest in sources.items()):
            raise ValueError('both retained proof packets must bind the routed candidate RTL')
        if not all(p.get(key) is True for key in ('enabled_decision_stable_at_sampled_falling_edge_in_actual_parent_proved',
                'disabled_output_seed_override_proved', 'decision_is_zero_at_each_sampled_loop_enable_assertion_proved',
                'actual_filter_output_mask_removed_mutation_rejected')):
            raise ValueError('completed integrated phase/mask/rearm proof and negative control required')
        if (s.get('initial_sampled_tracking_code_matches_seed_proved') is not True
                or g.get('all_recursive_layer_geometry_and_texts_match') is not True):
            raise ValueError('current seed proof and original macro geometry binding required')
        module = json.loads(mapped.read_text())['modules']['IntegerPLL_ProgrammedCore']
        report = inventory(module)
        states = {row['cell']: row for row in report['sequential_state']}
        roots = clock_roots(module)
        rows = json.loads((coverage / 'endpoints.json').read_text())
        missing_sets = [{row['pin'] for row in rows if row['corner'] == corner and row['check'] == kind and not row['reported']}
                        for corner in ('tt', 'ff', 'ss', 'sf', 'fs') for kind in ('recovery', 'removal')]
        if any(value != missing_sets[0] for value in missing_sets) or len(missing_sets[0]) != 54:
            raise ValueError('identical missing reset endpoint set across all views required')
        missing = []
        for pin in sorted(missing_sets[0]):
            name, terminal = pin.rsplit('/', 1)
            state = states[name]
            if terminal != state['asynchronous_control_pin']:
                raise ValueError('native async pin differs from mapped state')
            source_set = {(v['kind'], v['name']) for v in state['control_sources']}
            if source_set == {('primary_input', 'RESET_N')}:
                kind = 'external_RESET_N_only'
            elif ('primary_input', 'RESET_N') in source_set:
                kind = 'oscillator_reset_from_reference_domain'
            else:
                kind = 'event_capture_reset_from_fast_domain'
            control_clocks = [dict(source=v['name'], clock_root=roots(v['clock_bit']))
                              for v in state['control_sources'] if v['kind'] == 'sequential']
            missing.append(dict(pin=pin, classification=kind, clock_root=roots(state['clock_bit']),
                 state_aliases=state['output_aliases'], control_sources=state['control_sources'],
                 sequential_control_clock_roots=control_clocks, structurally_classified_only=True,
                 physical_reset_timing_or_waiver_qualified=False))
        counts = dict(Counter(row['classification'] for row in missing))
        if counts != dict(external_RESET_N_only=48, oscillator_reset_from_reference_domain=4,
                          event_capture_reset_from_fast_domain=2):
            raise ValueError('unexpected unreported reset-source groups')
        # Bind the phase assertion to the actual inverted decision-clock roots.
        decision_cells = []
        bits = module['netnames']['core.gen_registered_decision.decision_q']['bits']
        for bit in bits:
            matches = [(name, cell) for name, cell in module['cells'].items() if cell['connections'].get('Q') == [bit]]
            if len(matches) != 1:
                raise ValueError('unique registered decision bit required')
            name, cell = matches[0]
            root = roots(cell['connections']['CLK'][0])
            if root != ('sequential', '$auto$ff.cc:337:slice$18687', 'Q', 1):
                raise ValueError('decision clock polarity does not match sampled falling-edge proof')
            decision_cells.append(dict(cell=name, mapped_clock_root=root))
        files = [route, mapped, coverage / 'assessment.json', coverage / 'endpoints.json', mask, seed, reuse, equivalence, route_v,
                 Path(__file__).resolve(), Path(__file__).with_name('inventory_mapped_CDC.py'),
                 Path(__file__).with_name('compare_mapped_routed_CDC.py')]
        pins = {**sources, **{str(path): sha(path) for path in files}}
        verify(pins)
        detail = output / 'unreported_reset_endpoints.json'
        save(detail, missing)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
             unreported_endpoints_per_corner=54, unreported_classification_counts=counts,
             complete_missing_endpoint_set_classified=True, decision_clock_polarity_bound=decision_cells,
             retained_sampled_mask_and_rearm_proof_bound=True, retained_seed_proof_bound=True,
             original_macro_geometry_binding_retained=True, logical_proofs_newly_inducted=False,
             inherited_reset_and_async_exceptions_waived_by_this_binding=False,
             external_reset_pulse_width_qualified=False, metastability_resolution_qualified=False,
             startup_and_disable_reenable_physical_timing_qualified=False,
             clock_branch_ECO_selected=False, physical_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='retained_lifecycle_logic_bound_and_reset_omissions_classified', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
