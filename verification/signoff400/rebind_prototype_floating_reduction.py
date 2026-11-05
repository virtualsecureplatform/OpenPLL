"""Transfer a bounded floating-C reduction through a verified node bijection.

Native extraction and linear solves are reused only when the complete source
capacitor operators match exactly under the bijection. Devices and wire
resistors come unchanged from the target model.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
from common_v3 import save, sha, verify
from inventory_prototype_floating_C_components import components
from prepare_prototype_analog_reference import subcircuits
from check_prototype_capacitance_paths import certify
from project_prototype_fixed_rail_C_v2 import project, RAILS


def bijection(source, target):
    if source.keys() != target.keys():
        raise ValueError('original capacitance node sets differ')
    result = {}
    for original, a in source.items():
        b = target[original]
        if a in result and result[a] != b:
            raise ValueError('voltage mapping is not a function')
        result[a] = b
    if len(set(result.values())) != len(result):
        raise ValueError('voltage mapping is not bijective')
    for rail in RAILS:
        if rail in result and result[rail] != rail:
            raise ValueError('fixed rail moved')
    return result


def capacitor_pairs(text, mapping=None):
    pairs = {}
    for line in text.splitlines():
        f = line.split()
        if not f or not f[0].startswith(('Cflat', 'Ckron')):
            continue
        if len(f) != 4:
            raise ValueError('unexpected flat capacitor syntax')
        a, b = f[1:3]
        if mapping is not None:
            a, b = mapping[a], mapping[b]
        key = tuple(sorted((a, b)))
        pairs[key] = pairs.get(key, Fraction()) + Fraction(f[3])
    return {key: value for key, value in pairs.items() if value}


def run(models, reduced, source_nodes, target_nodes, output):
    receipts = [p/'assessment.json' for p in (models, reduced, source_nodes, target_nodes)]
    m, r, sn, tn = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    source_attachment, target_attachment = sn['attachment'], tn['attachment']
    if source_attachment == target_attachment or r['attachment'] != source_attachment:
        raise ValueError('distinct source and target attachments required')
    for n in (sn, tn):
        if not n.get('exact_completed_model_bytes_reproduced') or n['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
            raise ValueError('node maps must reproduce these completed models')
    if not r.get('bounded_floating_C_terminal_reduction_verified') or not r.get('all_primitive_and_wire_cards_unchanged'):
        raise ValueError('bounded source reduction required')
    for field in ('candidate_gds_sha256', 'assembled_candidate_gds_sha256'):
        if m[field] != r[field]:raise ValueError('physical candidate mismatch')
    original = models/(source_attachment+'.spice')
    if r['input_sha256'].get(str(original)) != sha(original):
        raise ValueError('reduction does not bind source model')
    paths = [source_nodes/'nodes.json', target_nodes/'nodes.json']
    target_path = models/(target_attachment+'.spice')
    inputs = {str(p): sha(p) for p in [*receipts, *paths, original, target_path, reduced/(source_attachment+'.spice'), reduced/'reduction_bounds.json', reduced/'node_inventory.json', Path(__file__).resolve(), *[Path(__file__).with_name(n) for n in ('inventory_prototype_floating_C_components.py', 'check_prototype_capacitance_paths.py', 'project_prototype_fixed_rail_C_v2.py')]]}
    a, b = [json.loads(p.read_text()) for p in paths]
    mapping = bijection(a['original_capacitance_node_to_emitted_node'], b['original_capacitance_node_to_emitted_node'])
    before, target = original.read_text(), target_path.read_text()
    if capacitor_pairs(before, mapping) != capacitor_pairs(target):
        raise ValueError('complete capacitor operators differ under claimed bijection')
    blocks = subcircuits(target)
    if len(blocks) != 1:raise ValueError('one flat target model required')
    top = next(iter(blocks))
    groups, _ = components(target, top)
    inventory = json.loads((reduced/'node_inventory.json').read_text())
    if len(groups) != 1 or {mapping[n] for n in inventory['floating_nodes']} != set(groups[0]['nodes']):
        raise ValueError('eliminated floating subspaces differ')
    if {mapping[n] for n in inventory['retained_boundaries']} != set(groups[0]['boundaries']):
        raise ValueError('retained boundary subspaces differ')
    source_reduced = (reduced/(source_attachment+'.spice')).read_text()
    caps = []
    for line in source_reduced.splitlines():
        f = line.split()
        if f and f[0].startswith(('Cflat', 'Ckron')):
            caps.append(' '.join((f[0], mapping[f[1]], mapping[f[2]], f[3])))
    lines = []
    for line in target.splitlines():
        f = line.split()
        if f and f[0].startswith('Cflat'):continue
        if f and f[0].lower() == '.ends':lines.extend(caps)
        lines.append(line)
    text = '\n'.join(lines)+'\n'
    if [l for l in target.splitlines() if l.startswith(('Xflat', 'Rwire'))] != [l for l in text.splitlines() if l.startswith(('Xflat', 'Rwire'))]:
        raise ValueError('target devices or wire resistors changed')
    pairs = capacitor_pairs(text)
    if pairs != capacitor_pairs(source_reduced, mapping):raise ValueError('reduced export operator differs')
    proof = certify(project(pairs, set(RAILS)))
    if not proof['passivity_certified']:raise ValueError('target reduction lacks passivity')
    output.mkdir(parents=True, exist_ok=False)
    model = output/(target_attachment+'.spice');model.write_text(text)
    save(output/'node_bijection.json', mapping)
    save(output/'fixed_rail_passivity.json', proof)
    bounds = json.loads((reduced/'reduction_bounds.json').read_text())
    bounds['row_node_names'] = [mapping[n] for n in inventory['retained_boundaries']]
    bounds['transfer_is_boundary_permutation'] = True
    save(output/'reduction_bounds.json', bounds)
    verify(inputs)
    fields = ('candidate_gds_sha256', 'assembled_candidate_gds_sha256', 'eliminated_capacitor_only_nodes', 'retained_boundary_nodes', 'relative_row_error_budget', 'maximum_normalized_row_error')
    save(output/'assessment.json', dict(input_sha256=inputs, artifacts={str(p):sha(p) for p in output.iterdir()},
        **{f:r[f] for f in fields}, attachment=target_attachment,
        bounded_floating_C_terminal_reduction_verified=True, all_primitive_and_wire_cards_unchanged=True,
        each_fixed_supply_dynamic_C_operator_passivity_certified=True,
        complete_source_capacitor_bijection_verified=True, boundary_permutation_error_bound_reused=True,
        numerical_reduction_with_explicit_error_bound=True, native_linear_solve_repeated=False,
        capacitance_lifts_are_exact_matrix_congruences=False,
        zero_wire_R_topology_and_capacitance_operator_identity_verified=False,
        native_reduced_model_correlation_complete=False, parent_loading_complete=False,
        FOM_fill_electrical_coverage_complete=False, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('models', 'reduced', 'source-nodes', 'target-nodes', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    run(*[getattr(a, n).resolve() for n in ('models', 'reduced', 'source_nodes', 'target_nodes', 'output')])
