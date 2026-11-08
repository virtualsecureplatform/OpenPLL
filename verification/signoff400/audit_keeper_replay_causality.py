"""Inventory prescribed transistor terminals; no dynamic independence claim."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify
from reduce_keeper_capacitor_boundaries import root_info


def inventory(text, bindings, observations):
    driven = bindings['externally_driven_ports']
    reverse = {v.lower(): k for k, v in driven.items()}
    if len(reverse) != len(driven):
        raise ValueError('duplicate prescribed native port')
    controls = {v['physical_node'] for v in observations.values() if v['endpoint'] == 'macro'}
    if not controls <= driven.keys():
        raise ValueError('physical programming endpoint missing')
    _, _, _, cards = root_info(text)
    uses = {k: [] for k in driven}
    observed = {v.lower() for v in bindings['observation_only_ports'].values()}
    feedback = []
    for _, fields in cards:
        if fields[0][0].upper() != 'X':
            continue
        for position, node in enumerate(fields[1:-1]):
            if node.lower() in reverse:
                uses[reverse[node.lower()]].append(dict(primitive=fields[0], terminal_position=position, wrapper=fields[-1]))
        # A four-terminal MOS wrapper whose gate is observed and D/S is forced.
        # Report positions explicitly: wrapper semantics must be checked separately.
        if len(fields) == 6 and fields[2].lower() in observed:
            for position in (0, 2):
                node = fields[position + 1].lower()
                if node in reverse and reverse[node] not in {'VPWR', 'VGND'}:
                    feedback.append(dict(primitive=fields[0], observed_gate=fields[2], prescribed_terminal=reverse[node], terminal_position=position, wrapper=fields[-1]))
    roles = {}
    for key in driven:
        role = ('programming_macro_endpoint' if key in controls else
                'supply' if key in {'VPWR', 'VGND'} else
                'reset' if key.endswith('.RESET_N') else
                'aggregate_capacitor_forcing' if key in bindings.get('synthetic_forcing_nodes', {}) else
                'other_prescribed_boundary')
        roles[key] = dict(role=role, native_port=driven[key], primitive_terminal_uses=uses[key])
    return dict(ports=roles, role_counts={role: sum(r['role'] == role for r in roles.values()) for role in sorted({r['role'] for r in roles.values()})}, observed_gate_to_prescribed_terminal_calls=feedback,
                conditional_environment_required=True, changed_controller_prediction_qualified=False,
                dynamic_error_qualified=False, model_qualified=False, release_ready=False)


def run(reduction, physical, output):
    if output.exists():
        raise FileExistsError(output)
    receipt = json.loads((reduction / 'assessment.json').read_text())
    verify(receipt['artifacts'])
    pa = json.loads((physical / 'assessment.json').read_text())
    # Bind to the completed physical assessment and its plan without rewriting them.
    if pa.get('native_completed') is not True or pa.get('all_macro_and_DCO_tuning_bits_match') is not True or pa.get('mismatched_endpoints') != 0:
        raise ValueError('completed physical assessment required')
    paths = [reduction / n for n in ('assessment.json', 'bindings.json', 'model.spice')]
    paths += [physical / n for n in ('assessment.json', 'plan.json', 'checks.json')]
    paths += [Path(__file__).resolve(), Path(__file__).with_name('reduce_keeper_capacitor_boundaries.py')]
    pins = {str(p): sha(p) for p in paths}
    result = inventory((reduction / 'model.spice').read_text(), json.loads((reduction / 'bindings.json').read_text()), json.loads((physical / 'plan.json').read_text())['observations'])
    verify(pins)
    save(output, dict(input_sha256=pins, **result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('reduction', 'physical', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, name).resolve() for name in ('reduction', 'physical', 'output')))
