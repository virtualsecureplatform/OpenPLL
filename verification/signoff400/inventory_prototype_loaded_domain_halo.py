"""Inventory one complete-cell conductive halo around the loaded domain.

This selects actual incident devices; it supplies no boundary voltages and
does not replace omitted drivers, receivers or capacitive loads.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from common_v3 import save, sha, verify
from inventory_prototype_context_domains import classify
from prepare_prototype_context_domain_reference import partition


def select(terminals, cells, base, fixed):
    if terminals.keys() != cells.keys() or not base <= terminals.keys():
        raise ValueError('complete matching physical-cell and primitive inventories required')
    _, cuts = partition(terminals, base, fixed)
    halo_cells = {cells[name] for name in terminals.keys() - base
                  if set(terminals[name]) & cuts}
    expanded = base | {name for name, cell in cells.items() if cell in halo_cells}
    private, remaining = partition(terminals, expanded, fixed)
    return expanded, cuts, private, remaining


def run(reference, frame, output):
    receipts = [p / 'assessment.json' for p in (reference, frame)]
    rr, fr = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    metadata_file = reference / 'nodes.json'
    model = reference / 'context.spice'
    metadata = json.loads(metadata_file.read_text())
    roles, cells = classify(metadata['physical_instances'],
                            {k: v['master'] for k, v in fr['macro_sources'].items()})
    terminals = {}
    for line in model.open():
        if not line.startswith('Xflat'):
            continue
        fields = line.split()
        stop = next(i for i, f in enumerate(fields) if f.startswith('sky130_fd_pr__'))
        if fields[0] in terminals:
            raise ValueError('duplicate primitive')
        terminals[fields[0]] = fields[1:stop]
    receiver_cells = {cells[n] for n, nodes in terminals.items()
                      if roles[n] == 'digital' and 'PLLOUT' in nodes}
    base = {n for n, role in roles.items()
            if role in ('parent', 'oscillator') or cells[n] in receiver_cells}
    fixed = {metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes']} | {'0'}
    expanded, cuts, private, remaining = select(terminals, cells, base, fixed)
    incident = {node: sorted(n for n in terminals.keys() - expanded if node in terminals[n])
                for node in sorted(remaining)}
    masters = {r['instance']: r['leaf_master'] for r in metadata['physical_instances']}
    added_cell_masters = {}
    for name in expanded - base:
        cell, master = cells[name], masters[name]
        if cell in added_cell_masters and added_cell_masters[cell] != master:
            raise ValueError('one physical cell has conflicting masters')
        added_cell_masters[cell] = master
    paths = [*receipts, metadata_file, model, Path(__file__).resolve(),
             Path(__file__).with_name('inventory_prototype_context_domains.py'),
             Path(__file__).with_name('prepare_prototype_context_domain_reference.py')]
    pins = {str(p): sha(p) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    detail = output / 'halo.json'
    save(detail, dict(base_primitives=sorted(base), added_primitives=sorted(expanded - base),
                     expanded_primitives=sorted(expanded), private_nodes=sorted(private),
                     original_conductive_cuts=sorted(cuts),
                     remaining_conductive_cuts=incident,
                     added_whole_cell_masters=dict(Counter(added_cell_masters.values()))))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         base_primitives=len(base), base_conductive_cuts=len(cuts),
         added_primitives=len(expanded - base), expanded_primitives=len(expanded),
         added_physical_cells=len({cells[n] for n in expanded - base}),
         expanded_roles=dict(Counter(roles[n] for n in expanded)),
         retained_private_nodes=len(private), remaining_conductive_cuts=len(remaining),
         complete_incident_physical_cells_selected=True, fixed_rails_excluded_from_halo=True,
         direction_classification_performed=False, boundary_waveforms_supplied=False,
         remote_capacitor_endpoints_grounded=False, model_deck_exported=False,
         loaded_native_model_qualified=False, diagnostic=True,
         validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'frame', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference.resolve(), args.frame.resolve(), args.output.resolve())
