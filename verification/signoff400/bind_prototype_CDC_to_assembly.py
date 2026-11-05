"""Bind every routed synchronizer interstage cell and conductor to filled-GDS LVS extraction."""
import argparse
import json
from pathlib import Path

from bind_prototype_spef_pins_v2 import hierarchy
from common import save, sha, verify


def bind(chains, mapping, text):
    _, cells, canonical = hierarchy(text, 'IntegerPLL_ProgrammedCore')
    route_to_extract = {}
    extract_to_route = {}
    results = []
    for chain in chains:
        bound = []
        for cell in chain['cells']:
            physical = cell['physical']
            row = mapping[physical['instance']]
            if row['master'] != physical['master']:
                raise ValueError('CDC physical master mismatch')
            extracted = cells[row['extracted_instance']]
            if extracted['model'] != row['master']:
                raise ValueError('extracted CDC model mismatch')
            pins = {}
            for pin, routed in physical['pins'].items():
                node = canonical(extracted['pins'][pin])
                net = routed['net']
                if route_to_extract.setdefault(net, node) != node:
                    raise ValueError('routed CDC conductor split in assembly extraction')
                if extract_to_route.setdefault(node, net) != net:
                    raise ValueError('distinct routed CDC conductors shorted in assembly extraction')
                pins[pin] = dict(routed_net=net, extracted_node=node)
            bound.append(dict(routed_instance=physical['instance'],
                              extracted_instance=row['extracted_instance'], master=row['master'], pins=pins))
        for index, (left, right) in enumerate(zip(bound, bound[1:])):
            source = chain['cells'][index]['output_pin']
            # Endpoint stages and all intermediate buffers carry explicit pin roles.
            destination = chain['cells'][index + 1]['input_pin']
            if left['pins'][source]['extracted_node'] != right['pins'][destination]['extracted_node']:
                raise ValueError('interstage conductor is discontinuous in assembly extraction')
        results.append(dict(id=chain['id'], role=chain['role'], cells=bound))
    if not results:
        raise ValueError('no synchronizers supplied')
    return dict(chains=results, distinct_interstage_conductors=len(route_to_extract),
                physical_cells=sum(len(c['cells']) for c in results))


def run(layout, joined, routed, output):
    output.mkdir(parents=True, exist_ok=False)
    lr, jr, rr = [p / 'assessment.json' for p in (layout, joined, routed)]
    l, j, r = [json.loads(p.read_text()) for p in (lr, jr, rr)]
    source, mapping, chains = layout / 'assembly.spice', joined / 'join.json', routed / 'binding.json'
    if l.get('assembled_lvs_pass') is not True or j.get('all_instance_placements_match') is not True:
        raise ValueError('passing assembly LVS and exact placement join required')
    if r.get('all_interstage_cells_pins_and_nets_physically_bound') is not True:
        raise ValueError('complete routed interstage binding required')
    if j['input_sha256'].get(str(source)) != sha(source):
        raise ValueError('placement join uses another extracted assembly')
    verify(j['input_sha256'])
    for path, receipt in ((source, l), (mapping, j), (chains, r)):
        if receipt['artifacts'].get(str(path)) != sha(path):
            raise ValueError('binding source changed')
    paths = [lr, jr, rr, source, mapping, chains, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    rows = json.loads(mapping.read_text())['mapping']
    keyed = {row['routed_instance']: row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError('ambiguous physical instance join')
    result = bind(json.loads(chains.read_text())['chains'], keyed, source.read_text())
    detail = output / 'binding.json'
    save(detail, result)
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         all_interstage_cells_bound_to_filled_GDS_extraction=True,
         all_interstage_conductor_equivalences_match=True,
         synchronizers=len(result['chains']), physical_cells=result['physical_cells'],
         delay_or_metastability_qualified=False, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('layout', 'joined', 'routed', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.layout.resolve(), a.joined.resolve(), a.routed.resolve(), a.output.resolve())
