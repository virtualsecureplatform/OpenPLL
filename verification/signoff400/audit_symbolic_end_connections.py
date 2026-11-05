"""Audit direct device/port incidence of unresolved constrained sheet-end states."""
import argparse
import json
import struct
from pathlib import Path
from common import save, sha


def scan_devices(path, remap, targets):
    hits = []
    devices = terminals = 0
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            devices += 1
            for terminal, private, voltage, printed in row['terminals']:
                if not 0 <= voltage < len(remap):
                    raise ValueError('device voltage out of bounds')
                terminals += 1
                target = remap[voltage]
                if target in targets:
                    hits.append(dict(model=row['model'], terminal=terminal,
                                     private_id=private, printed_name=printed,
                                     constrained_voltage_id=target))
    return devices, terminals, hits


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    base = Path('build/signoff400').resolve()
    coverage = base/'startup_timing_G_parameter_coverage_audit_001/assessment.json'
    device = base/'startup_timing_final_device_basis_audit_001/assessment.json'
    ports = base/'startup_timing_external_port_binding_001/assessment.json'
    zero = base/'startup_timing_zero_R_voltage_map_002/assessment.json'
    proofs = [coverage, device, ports, zero]
    c, d, p, z = [json.loads(f.read_text()) for f in proofs]
    unresolved = coverage.parent/'unresolved_constrained_voltage_ids.json'
    joins = device.parent/'native_device_terminal_join.jsonl'
    port_rows = ports.parent/'ports.json'
    mapping = zero.parent/'voltage_map.bin'
    paths = [*proofs, unresolved, joins, port_rows, mapping, Path(__file__).resolve()]
    pins = {str(f):sha(f) for f in paths}
    for proof, artifact in ((c,unresolved),(d,joins),(p,port_rows),(z,mapping)):
        if proof['artifacts'][str(artifact)] != pins[str(artifact)]:
            raise ValueError('parent artifact hash mismatch')
    if not d['all_final_native_device_terminals_independently_joined'] or not p['exact_native_external_port_binding_complete']:
        raise ValueError('incomplete parent binding')
    if c['input_sha256'].get(str(zero)) != pins[str(zero)]:
        raise ValueError('coverage used a different zero-R namespace')
    import array
    remap = array.array('I')
    with mapping.open('rb') as stream:
        if stream.read(8) != b'CNETDOF1': raise ValueError('mapping magic')
        original, constrained = struct.unpack('<QQ',stream.read(16))
        remap.fromfile(stream, original)
        if stream.read(1): raise ValueError('mapping trailing data')
    import sys
    if sys.byteorder != 'little': remap.byteswap()
    targets = set(json.loads(unresolved.read_text()))
    if len(targets) != c['unresolved_semiconductor_voltage_states'] or any(not 0 < n < constrained for n in targets):
        raise ValueError('unresolved state inventory')
    # Verify the detection path with a selected real terminal, then audit all actual targets.
    first = json.loads(joins.open().readline())['terminals'][0][2]
    count, terms, control = scan_devices(joins, remap, {remap[first]})
    if not control: raise ValueError('terminal incidence positive control failed')
    devices, terminals, hits = scan_devices(joins, remap, targets)
    if devices != d['native_exported_devices'] or terminals != d['native_exported_terminal_bindings']:
        raise ValueError('device scan coverage mismatch')
    bound_ports = json.loads(port_rows.read_text())
    port_hits=[]
    for row in bound_ports:
        if remap[row['original_voltage_id']] != row['constrained_voltage_id']:
            raise ValueError('port transform mismatch')
        if row['constrained_voltage_id'] in targets: port_hits.append(row)
    if len(bound_ports) != p['ports']: raise ValueError('port scan coverage mismatch')
    save(output/'direct_connections.json',dict(device_terminals=hits,external_ports=port_hits))
    if any(sha(f)!=pins[str(f)] for f in paths): raise ValueError('source changed')
    save(output/'assessment.json',dict(input_sha256=pins,
        artifacts={str(output/'direct_connections.json'):sha(output/'direct_connections.json')},
        all_native_device_terminals_and_external_ports_scanned=True,
        real_terminal_incidence_positive_control_passed=True,
        devices=devices,terminal_bindings=terminals,external_ports=len(bound_ports),
        unresolved_states=len(targets),direct_device_terminal_hits=len(hits),direct_external_port_hits=len(port_hits),
        capacitance_incidence_checked=False,unresolved_states_eliminable=False,
        physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    run(parser.parse_args().output.resolve())
