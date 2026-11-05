"""Bind native SPICE interface names to existing R nodes without name heuristics."""
import argparse
import json
import struct
from pathlib import Path
from common import save, sha


def header(path):
    ports = None
    with path.open() as stream:
        for line in stream:
            if line.lower().startswith('.subckt '):
                if ports is not None:
                    raise ValueError('multiple header starts')
                ports = line.split()[2:]
            elif ports is not None and line.startswith('+'):
                ports.extend(line.split()[1:])
            elif ports is not None:
                break
    if not ports or len(set(ports)) != len(ports):
        raise ValueError('missing or duplicate interface ports')
    return ports


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path.cwd()
    core_proof = root/'build/signoff400/startup_timing_final_native_R_core_002/assessment.json'
    zero_proof = root/'build/signoff400/startup_timing_zero_R_voltage_map_002/assessment.json'
    mapping = zero_proof.parent/'voltage_map.bin'
    nodes = Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    trace = Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace')
    decks = [trace/'pre_resistance.spice', trace/'retained_rc.spice']
    paths = [core_proof, zero_proof, mapping, nodes, *decks, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    core, zero = [json.loads(p.read_text()) for p in (core_proof, zero_proof)]
    if core['artifacts'][str(nodes)] != pins[str(nodes)]:
        raise ValueError('native node artifact differs')
    if zero['artifacts'][str(mapping)] != pins[str(mapping)]:
        raise ValueError('zero-R mapping differs')
    ports = header(decks[0])
    if ports != header(decks[1]):
        raise ValueError('pre/post extraction interface differs')
    lookup = {name: [] for name in ports}
    with nodes.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['printed_name'] in lookup:
                lookup[row['printed_name']].append(row)
    if any(len(rows) != 1 for rows in lookup.values()):
        raise ValueError('missing or ambiguous exact native interface name')
    rows = []
    with mapping.open('rb') as stream:
        if stream.read(8) != b'CNETDOF1':
            raise ValueError('mapping format')
        original, constrained = struct.unpack('<QQ', stream.read(16))
        if mapping.stat().st_size != 24+4*original:
            raise ValueError('mapping size')
        for index, name in enumerate(ports):
            row = lookup[name][0]
            voltage = row['global_voltage_id']
            if not 0 < voltage < original:
                raise ValueError('port voltage bounds/reference')
            stream.seek(24+4*voltage)
            target, = struct.unpack('<I', stream.read(4))
            if not 0 < target < constrained:
                raise ValueError('constrained port voltage bounds/reference')
            rows.append(dict(port_index=index, port_name=name, original_voltage_id=voltage,
                             constrained_voltage_id=target, native_private_id=row['private_id'],
                             native_group_id=row['native_group_id'], point_internal=row['point_internal']))
    save(output/'ports.json', rows)
    if any(sha(p) != pins[str(p)] for p in paths):
        raise ValueError('input changed during binding')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str((output/'ports.json').resolve()):sha(output/'ports.json')},
         exact_native_external_port_binding_complete=True, ports=len(rows),
         original_distinct_voltage_ids=len({r['original_voltage_id'] for r in rows}),
         constrained_distinct_voltage_ids=len({r['constrained_voltage_id'] for r in rows}),
         spatial_projection_final_receipt_reconciled=False,
         whole_circuit_binding_complete=False, physical_model_qualified=False,
         release_qualified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
