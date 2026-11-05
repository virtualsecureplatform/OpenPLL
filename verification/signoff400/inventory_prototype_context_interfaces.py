"""Resolve cone cuts against same-extraction macro ports and physical LEF directions.

Directions describe boundary obligations only; they do not validate stimuli,
replace receiver devices, or authorize grounding remote capacitor endpoints.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from common_v3 import save, sha, verify
from bind_prototype_spef_pins_v2 import hierarchy


def lef_directions(text):
    result = {}
    pin = None
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == 'PIN':
            if pin is not None or fields[1] in result:
                raise ValueError('duplicate or nested LEF pin')
            pin = fields[1]
        elif pin is not None and fields[:1] == ['DIRECTION']:
            if pin in result:
                raise ValueError('duplicate LEF pin direction')
            direction = fields[1].rstrip(';')
            if direction not in ('INPUT', 'OUTPUT', 'INOUT'):
                raise ValueError('unsupported physical pin direction')
            result[pin] = direction
        elif pin is not None and fields == ['END', pin]:
            if pin not in result:
                raise ValueError('missing physical pin direction')
            pin = None
    if pin is not None or not result:
        raise ValueError('incomplete physical pin inventory')
    return result


def obligations(endpoints):
    # A macro OUTPUT outside the cone drives it; an INPUT outside receives it.
    directions = {e['direction'] for e in endpoints if e['role'] != 'oscillator'}
    if directions == {'OUTPUT'}:
        return 'external_driver_required'
    if directions == {'INPUT'}:
        return 'receiver_devices_and_loading_required'
    if directions == {'INPUT', 'OUTPUT'}:
        return 'external_driver_and_receiver_loading_required'
    return 'unresolved_or_bidirectional'


def run(reference, converted, domains, frame, output):
    receipts = [p / 'assessment.json' for p in (reference, converted, domains, frame)]
    rr, cr, dr, fr = [json.loads(p.read_text()) for p in receipts]
    metadata_path = reference / 'nodes.json'
    domain_path = domains / 'domains.json'
    source = converted / 'ng47.spice'
    for path, receipt in ((metadata_path, rr), (domain_path, dr), (source, cr)):
        if receipt['artifacts'].get(str(path)) != sha(path):
            raise ValueError('changed inventoried input: ' + str(path))
    if rr['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
        raise ValueError('flat reference and converted hierarchy differ')
    if dr['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('domain inventory and flat reference differ')
    if dr['input_sha256'].get(str(receipts[3])) != sha(receipts[3]):
        raise ValueError('physical frame differs from domain inventory')
    metadata = json.loads(metadata_path.read_text())
    domain = json.loads(domain_path.read_text())
    top = rr['top']
    ports, instances, find = hierarchy(source.read_text(), top)
    paths = [*receipts, metadata_path, domain_path, source, Path(__file__).resolve(),
             Path(__file__).with_name('bind_prototype_spef_pins_v2.py'),
             Path(__file__).with_name('prepare_prototype_analog_reference.py'),
             Path(__file__).with_name('audit_hierarchical_capacitance.py')]
    endpoints = defaultdict(list)
    for role, macro in fr['macro_sources'].items():
        lef = Path(macro['lef'])
        paths.append(lef)
        if fr['input_sha256'].get(str(lef)) != sha(lef):
            raise ValueError('physical LEF differs from frame')
        directions = lef_directions(lef.read_text())
        matches = [i for i in instances.values() if i['model'] == macro['master']]
        if len(matches) != 1:
            raise ValueError('one same-extraction macro instance required')
        for pin, direction in directions.items():
            # Native extraction can merge physical bulk/power ports. This
            # inventory resolves signal cuts; fixed rails are excluded there.
            if pin in ('VGND', 'VNB', 'VPB', 'VPWR'):
                continue
            if pin not in matches[0]['pins']:
                raise ValueError('physical pin missing from native extraction: ' + pin)
            node = find(matches[0]['pins'][pin])
            original = node if node in ports or node == '0' else top + '/' + node
            compact = metadata['original_to_emitted'][original]
            endpoints[compact].append(dict(role=role, pin=pin, direction=direction))
    pins = {str(p): sha(p) for p in paths}
    rows = []
    for node, primitives in sorted(domain['cone_cut_conductors'].items()):
        ep = endpoints.get(node, [])
        rows.append(dict(node=node, macro_endpoints=ep,
                         outside_primitive_count=len(primitives),
                         obligation=obligations(ep)))
    counts = Counter(r['obligation'] for r in rows)
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    detail = output / 'interfaces.json'
    save(detail, dict(cuts=rows, remote_capacitor_terminals=domain['cone_remote_capacitor_terminals']))
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
        cut_conductors=len(rows), obligations=dict(counts),
        same_extraction_port_binding=True, physical_LEF_directions_used=True,
        all_cuts_have_unambiguous_direction_obligations=not counts['unresolved_or_bidirectional'],
        receiver_devices_removed=False, remote_terminals_grounded=False,
        interface_stimuli_validated=False, loaded_native_model_qualified=False,
        diagnostic=True, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'converted', 'domains', 'frame', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, n).resolve() for n in ('reference', 'converted', 'domains', 'frame', 'output')))
