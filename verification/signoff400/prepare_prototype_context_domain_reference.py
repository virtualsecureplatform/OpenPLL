"""Export a conditional loaded-oscillator reference without inventing stimuli.

Retains all oscillator and parent primitives plus complete PLLOUT receiver
cells. Boundary voltages remain explicit ports. Capacitors contributing only
to boundary currents are exported separately, never replaced by ground loads.
This is an exact partition of the guarded model, not a qualified domain model.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from common_v3 import save, sha, verify


def partition(terminals, selected, fixed):
    inside = {n for name in selected for n in terminals[name]} - set(fixed)
    outside = {n for name in terminals.keys() - selected for n in terminals[name]} - set(fixed)
    cuts = inside & outside
    return inside - cuts, cuts


def header(name, ports):
    rows = ['.subckt ' + name]
    for i in range(0, len(ports), 16):
        rows.append('+ ' + ' '.join(ports[i:i + 16]))
    return '\n'.join(rows) + '\n'


def cards(path):
    for line in path.open():
        fields = line.split()
        if fields and fields[0].startswith(('Xflat', 'Cflat', 'Ckron', 'Rwire')):
            yield fields, line.rstrip('\n')


def run(reference, reduced, domains, interfaces, output):
    receipts = [p / 'assessment.json' for p in (reference, reduced, domains, interfaces)]
    rr, gr, dr, ir = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    if gr['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('guarded model reference differs')
    if dr['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
        raise ValueError('domain inventory model differs')
    if ir['input_sha256'].get(str(receipts[2])) != sha(receipts[2]):
        raise ValueError('interface inventory domain differs')
    if not gr['complete_reduced_fixed_supply_C_passivity_certified']:
        raise ValueError('complete passive guarded reference required')
    model = reduced / 'context.spice'
    detail_path = domains / 'domains.json'
    interface_path = interfaces / 'interfaces.json'
    metadata_path = reference / 'nodes.json'
    d = json.loads(detail_path.read_text())
    interface = json.loads(interface_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    terminals, primitive_cards = {}, {}
    for fields, line in cards(model):
        if fields[0].startswith('Rwire'):
            raise ValueError('wire/alias partition needs an explicit resistor interface')
        if fields[0].startswith('Xflat'):
            stop = next(i for i, word in enumerate(fields) if word.startswith('sky130_fd_pr__'))
            terminals[fields[0]] = fields[1:stop]
            primitive_cards[fields[0]] = line
    if terminals.keys() != d['primitive_roles'].keys():
        raise ValueError('primitive inventory differs')
    receiver_cuts = [r for r in interface['cuts']
                     if r['obligation'] == 'receiver_devices_and_loading_required']
    if len(receiver_cuts) != 1 or receiver_cuts[0]['node'] != 'PLLOUT':
        raise ValueError('one proved PLLOUT receiver boundary required')
    receiver_incident = d['cone_cut_conductors']['PLLOUT']
    receiver_cells = {d['physical_cells'][name] for name in receiver_incident}
    receiver = {name for name, cell in d['physical_cells'].items() if cell in receiver_cells}
    selected = {name for name, role in d['primitive_roles'].items()
                if role in ('oscillator', 'parent')} | receiver
    private, cuts = partition(terminals, selected, set(d['fixed_supply_nodes']))
    main_caps, boundary_caps = [], []
    main_nodes = {n for name in selected for n in terminals[name]}
    boundary_nodes = set()
    source_caps = Counter()
    for fields, line in cards(model):
        if not fields[0].startswith('C'):
            continue
        if len(fields) != 4:
            raise ValueError('explicit constant capacitance required')
        source_caps[line] += 1
        if set(fields[1:3]) & private:
            main_caps.append(line); main_nodes.update(fields[1:3])
        else:
            boundary_caps.append(line); boundary_nodes.update(fields[1:3])
    ports = sorted(main_nodes - private)
    observations = sorted(private & set(d['named_top_ports']))
    # Observed outputs remain unknowns. Exporting an observation pin does not
    # prescribe its voltage or omit its capacitor contributions from KCL.
    main_ports = sorted(set(ports) | set(observations))
    outside_cards = [line for name, line in primitive_cards.items() if name not in selected]
    outside_nodes = sorted({n for name in terminals.keys() - selected for n in terminals[name]})
    paths = [*receipts, model, detail_path, interface_path, metadata_path, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    main = output / 'oscillator.spice'
    boundary = output / 'boundary_capacitance.spice'
    outside = output / 'exterior_devices.spice'
    main.write_text(header('ContextLoadedOscillator', main_ports) +
                    '\n'.join([primitive_cards[n] for n in sorted(selected)] + main_caps) +
                    '\n.ends ContextLoadedOscillator\n')
    boundary.write_text(header('ContextBoundaryCapacitance', sorted(boundary_nodes)) +
                        '\n'.join(boundary_caps) + '\n.ends ContextBoundaryCapacitance\n')
    outside.write_text(header('ContextExteriorDevices', outside_nodes) +
                       '\n'.join(outside_cards) + '\n.ends ContextExteriorDevices\n')
    # Reparse the actual exported cards independently. Joining equal conductor
    # identifiers restores every device and capacitance byte-for-byte.
    emitted_caps = Counter(line for p in (main, boundary) for fields, line in cards(p)
                           if fields[0].startswith('C'))
    emitted_primitives = Counter(line for p in (main, outside) for fields, line in cards(p)
                                 if fields[0].startswith('Xflat'))
    if emitted_caps != source_caps or emitted_primitives != Counter(primitive_cards.values()):
        raise ValueError('exported partition does not reconstruct full native cards')
    if any(set(fields[1:3]) & private for fields, _ in cards(boundary)):
        raise ValueError('private-node capacitance lost to boundary-current network')
    contract = output / 'interface_contract.json'
    save(contract, dict(selected_primitives=sorted(selected), receiver_primitives=sorted(receiver),
        private_KCL_nodes=sorted(private), conductive_cut_nodes=sorted(cuts),
        required_boundary_voltage_ports=ports, observation_ports_with_unknown_voltage=observations,
        oscillator_ports=main_ports, boundary_capacitance_ports=sorted(boundary_nodes),
        exterior_device_ports=outside_nodes,
        condition='Private-node KCL matches the complete guarded reference only under identical boundary voltage trajectories.',
        boundary_voltage_trajectories_supplied=False, complete_exterior_device_network_preserved=True))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in (main, boundary, outside, contract)},
        selected_primitive_count=len(selected), receiver_whole_cell_primitives=len(receiver),
        exterior_primitive_count=len(outside_cards), private_KCL_nodes=len(private),
        conductive_cut_nodes=len(cuts), required_boundary_voltage_ports=len(ports),
        main_capacitors=len(main_caps), boundary_current_only_capacitors=len(boundary_caps),
        all_source_primitive_and_C_cards_reconstructed=True,
        all_private_node_C_KCL_terms_preserved=True, boundary_current_network_preserved=True,
        whole_parent_and_receiver_cells_retained=True,
        remote_terminals_grounded=False, interface_stimuli_validated=False,
        standalone_native_domain_model=False, distributed_wire_R_added=False,
        loaded_native_model_qualified=False, diagnostic=True,
        validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('reference', 'reduced', 'domains', 'interfaces', 'output')
    for name in names:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, n).resolve() for n in names))
