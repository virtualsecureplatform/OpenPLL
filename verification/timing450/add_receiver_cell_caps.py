#!/usr/bin/env python3
"""Add LVS-checked GDS cell capacitance models to a diagnostic receiver fixture."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subcircuits(text):
    return {name: (ports.split(), body) for name, ports, body in re.findall(
        r'^\.subckt (\S+) ([^\n]+)\n([\s\S]*?)^\.ends[^\n]*$', text, re.M)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--cell-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    cells = args.cell_directory.resolve()
    source = fixture / 'receiver.spice'
    original = source.read_text()
    definitions = subcircuits(original)
    types_file = cells / 'selected_types.json'
    types = json.loads(types_file.read_text())
    assert set(definitions) == {'bbpd_receiver_cdc', *types}
    pins = {str(p): sha(p) for p in (source, fixture / 'extraction.json', types_file,
                                    cells / 'extract.tcl', Path(__file__).resolve())}
    base = Path(__file__).resolve().parents[2]
    pdk = base / 'build/timing450/pdk/sky130A'
    provenance = [cells / 'magic.log', cells / 'lvs_runner.log',
                  pdk / 'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds',
                  pdk / 'libs.tech/magic/sky130A.magicrc',
                  pdk / 'libs.tech/magic/sky130A.tech',
                  pdk / 'libs.tech/netgen/sky130A_setup.tcl']
    provenance.extend(cells.glob('cell_cap_*.ext'))
    provenance.extend(cells.glob('*.lvs.tcl'))
    for path in provenance:
        pins[str(path)] = sha(path)
    extraction = json.loads((fixture / 'extraction.json').read_text())
    for name, digest in extraction['sha256'].items():
        path = Path(name)
        assert sha(path) == digest, ('Stale fixture input', name)
        pins[name] = digest
    replacement = []
    counts = {}
    for index, typ in enumerate(types):
        model = cells / (typ + '.spice')
        log = cells / (typ + '.lvs.log')
        report = cells / (typ + '.lvs.json')
        native = cells / (typ + '.native.log')
        for path in (model, log, report, native, cells / (typ + '.mos.spice')):
            pins[str(path)] = sha(path)
        text = log.read_text()
        assert 'Final result: Circuits match uniquely.' in text
        assert 'Property errors were found.' not in text
        comparisons = json.loads(report.read_text())
        matches = [entry for entry in comparisons if entry.get('name') == ['cell_cap_' + str(index), typ]]
        assert len(matches) == 1
        comparison = matches[0]
        assert not comparison.get('badnets') and not comparison.get('badelements')
        assert comparison['devices'][0] == comparison['devices'][1]
        extracted = subcircuits(model.read_text())
        assert len(extracted) == 1
        ports, body = extracted['cell_cap_' + str(index)]
        original_ports = definitions[typ][0]
        assert len(ports) == len(set(ports)) and set(ports) == set(original_ports)
        counts[typ] = sum(line.startswith('C') for line in body.splitlines())
        assert counts[typ] > 0 and not any(line.startswith('R') for line in body.splitlines())
        alias = typ + '__gds_cap_model'
        replacement.append(f'.subckt {typ} {" ".join(original_ports)}\n'
                           f'Xphysical {" ".join(ports)} {alias}\n.ends {typ}\n'
                           f'.subckt {alias} {" ".join(ports)}\n{body}.ends {alias}\n')
    negative = cells / 'negative_width.lvs.log'
    assert 'Property errors were found.' in negative.read_text()
    for path in (negative, cells / 'negative_width.spice', cells / 'negative_width.lvs.json'):
        pins[str(path)] = sha(path)
    # Keep the entire mapped cone and its external RC byte-for-byte.
    match = re.search(r'^\.ends bbpd_receiver_cdc[^\n]*\n', original, re.M)
    assert match is not None
    prefix = original[:match.end()]
    result = prefix + '\n' + '\n'.join(replacement)
    assert subcircuits(result)['bbpd_receiver_cdc'] == definitions['bbpd_receiver_cdc']
    assert all(sha(Path(name)) == digest for name, digest in pins.items())
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output / 'receiver.spice'
    target.write_text(result)
    assessment = {'sha256': pins, 'receiver_sha256': sha(target),
                  'cell_capacitors': counts, 'cell_topology_width_length_lvs_pass': True,
                  'wrong_width_control_rejected': True, 'mapped_cone_and_external_rc_unchanged': True,
                  'release_qualified': False, 'selected': False,
                  'limitations': ['Nominal Magic cell capacitance with 0.01 fF threshold; no cell internal resistance',
                                  'LVS does not compare junction area/perimeter; extracted GDS geometry is retained',
                                  'No statistical metastability, supply noise, full reset network or whole-PLL proof']}
    (args.output / 'extraction.json').write_text(json.dumps(assessment, indent=2) + '\n')
    print(json.dumps({'cell_types': len(types), 'explicit_cell_capacitors': sum(counts.values()),
                      'receiver_sha256': sha(target)}, indent=2))


if __name__ == '__main__':
    main()
