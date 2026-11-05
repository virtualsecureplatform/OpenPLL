#!/usr/bin/env python3
"""Audit generated receiver bindings and inventory; no native qualification."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(text, result, model_ports):
    lines = [line.split() for line in text.splitlines() if line and line[0] != '*']
    instances = {f[0]: f for f in lines if f[0].lower().startswith('x')}
    assert len(instances) == len(result['selected_cells']) == 14
    bindings = 0
    for cell in result['selected_cells']:
        f = instances[cell['spice_instance']]
        assert f[-1] == cell['master']
        ports = model_ports[cell['master']]
        assert len(f[1:-1]) == len(ports)
        actual = dict(zip(ports, f[1:-1]))
        for pin in ('VGND', 'VNB', 'VPB', 'VPWR'):
            assert actual.pop(pin) == pin
        assert actual == cell['bindings']
        bindings += len(actual)
    assert bindings == 34
    counts = Counter(f[0].lower().rstrip('0123456789') for f in lines)
    for prefix, key in [('rwire', 'wire_resistors'), ('cground', 'ground_caps'),
                        ('ccoupled', 'coupling_caps')]:
        assert counts[prefix] == result[key]
    assert counts['cleaf'] == len(result['external_pin_capacitances']) == 4
    identifiers = [f[0].casefold() for f in lines if f[0][0].lower() in 'xrc']
    assert len(set(identifiers)) == len(identifiers)
    assert len(result['net_metrics']) == 17
    assert all(n['all_endpoints_connected'] for n in result['net_metrics'])
    return bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    report_path = args.fixture / 'assessment.json'
    report = json.loads(report_path.read_text())
    pins = {**report['input_sha256'], **report['artifacts']}
    for path, digest in pins.items():
        assert sha(path) == digest, path
    model_ports = {}
    for path in pins:
        if path.endswith('.spice'):
            for name, ports in re.findall(r'^\.subckt\s+(\S+)\s+([^\n]+)',
                                          Path(path).read_text(), re.M | re.I):
                if name.startswith('sky130_fd_sc_hs__'):
                    assert name not in model_ports
                    model_ports[name] = ports.split()
    results = []
    for result in report['results']:
        text = Path(result['fixture']).read_text()
        assert check(text, result, model_ports) == 34
        # Mutate only in-memory copies; never change a pinned fixture.
        mutations = [text.replace('Xcell0 VNB', 'Xcell0 VPB', 1),
                     re.sub(r'^Rwire0 .*\n', '', text, count=1, flags=re.M),
                     re.sub(r'^Cleaf0 .*\n', '', text, count=1, flags=re.M)]
        for mutated in mutations:
            assert mutated != text
            try:
                check(mutated, result, model_ports)
            except AssertionError:
                pass
            else:
                raise AssertionError('corrupted fixture accepted')
        results.append(dict(rc=result['rc'], functional_bindings=34,
                            rejected_faults=['supply_pin', 'missing_wire', 'missing_leaf_load']))
    args.output.mkdir(parents=True)
    payload = dict(input_sha256={str(report_path): sha(report_path),
                                str(Path(__file__).resolve()): sha(__file__)},
                   results=results, native_simulations_added=0,
                   native_fixture_validated=False, physical_timing_qualified=False,
                   release_qualified=False)
    (args.output / 'assessment.json').write_text(json.dumps(payload, indent=2)+'\n')
    print('Audited 102 cell-pin bindings across three RC views; nine faults rejected.')


if __name__ == '__main__':
    main()
