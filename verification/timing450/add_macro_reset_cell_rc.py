#!/usr/bin/env python3
"""Add LVS-checked GDS cell resistance/capacitance models to a diagnostic receiver fixture."""
import argparse
import hashlib
import json
import re
from diode_translation_probe_v2 import translated_model
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
    parser.add_argument('--diode-directory', type=Path, required=True)
    parser.add_argument('--diode-qualification', type=Path, required=True)
    parser.add_argument('--corner', choices=('ss','tt','ff','sf','fs'), required=True)
    parser.add_argument('--temperature-c', type=int, choices=(-40,27,125), required=True)
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    cells = args.cell_directory.resolve()
    source = fixture / 'receiver.spice'
    original = source.read_text()
    definitions = subcircuits(original)
    types_file = cells / 'selected_types.json'
    types = json.loads(types_file.read_text())
    assert set(definitions) == {'bbpd_receiver_cdc', 'sky130_fd_sc_hs__diode_2', *types} and len(types)==168
    pins = {str(p): sha(p) for p in (source, fixture / 'extraction.json', types_file,
                                    cells / 'extract.tcl', Path(__file__).resolve())}
    base = Path(__file__).resolve().parents[2]
    pdk = base / 'build/timing450/pdk/sky130A'
    provenance = [cells / 'magic.log', cells / 'assessment.json',
                  pdk / 'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds',
                  pdk / 'libs.tech/magic/sky130A.magicrc',
                  pdk / 'libs.tech/magic/sky130A.tech',
                  pdk / 'libs.tech/netgen/sky130A_setup.tcl']
    provenance.extend(cells.glob('*.ext'))
    provenance.extend([base / 'verification/timing450/collapse_cell_rc.py', cells / 'model_counts.json',
                       Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic'),
                       Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')])
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
    resistor_counts = {}
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
        matches = [entry for entry in comparisons if entry.get('name') == [typ, typ]]
        assert len(matches) == 1
        comparison = matches[0]
        assert not comparison.get('badnets') and not comparison.get('badelements')
        assert comparison['devices'][0] == comparison['devices'][1]
        extracted = subcircuits(model.read_text())
        assert len(extracted) == 1
        ports, body = extracted[typ]
        original_ports = definitions[typ][0]
        assert len(ports) == len(set(ports)) and set(ports) == set(original_ports)
        counts[typ] = sum(line.startswith('C') for line in body.splitlines())
        resistor_counts[typ] = sum(line.startswith('R') for line in body.splitlines())
        assert counts[typ] > 0 and resistor_counts[typ] > 0
        alias = typ + '__gds_rc_model'
        replacement.append(f'.subckt {typ} {" ".join(original_ports)}\n'
                           f'Xphysical {" ".join(ports)} {alias}\n.ends {typ}\n'
                           f'.subckt {alias} {" ".join(ports)}\n{body}.ends {alias}\n')
    diode_dir=args.diode_directory.resolve()
    qualification=json.loads(args.diode_qualification.read_text())
    assert qualification['model_equivalence_screen_passed'] and not qualification['pll_release_qualified']
    for name,wanted in qualification['evidence_sha256'].items():
        assert sha(Path(name))==wanted,name
        pins[name]=wanted
    diode_receipt=json.loads((diode_dir/'assessment.json').read_text())
    assert diode_receipt['native_topology_area_perimeter_lvs_pass'] and diode_receipt['wrong_area_control_rejected'] and diode_receipt['wrong_perimeter_control_rejected']
    for name,wanted in diode_receipt['sha256'].items():
        assert sha(Path(name))==wanted,name
        pins[name]=wanted
    electrical=[Path(p) for p in qualification['evidence_sha256'] if p.endswith('/receiver_macro_reset_diode_translation_v2/summary.json')]
    assert len(electrical)==1
    grid=json.loads(electrical[0].read_text())
    assert grid['effective_geometry']=={'area_um2':.6417,'perimeter_um':3.24}
    aj,pj=grid['corner_parameters'][args.corner]
    physical=subcircuits((diode_dir/'sky130_fd_sc_hs__diode_2.spice').read_text())
    assert set(physical)=={'sky130_fd_sc_hs__diode_2'}
    port_order,body=physical['sky130_fd_sc_hs__diode_2']
    diode_lines=[line for line in body.splitlines() if line.startswith('X')]
    assert len(diode_lines)==1
    fields=diode_lines[0].split()
    assert fields[3]=='sky130_fd_pr__diode_pw2nd_05v5'
    params={k:float(v) for k,v in (field.split('=') for field in fields[4:])}
    assert params=={'perim':3.24e6,'area':6.417e11}
    changed='D0 '+' '.join(fields[1:3])+' macro_reset_diode_fixed area=.6417 pj=3.24'
    body=body.replace(diode_lines[0],changed)
    typ='sky130_fd_sc_hs__diode_2';alias=typ+'__gds_rc_model'
    logical_ports=definitions[typ][0]
    assert set(logical_ports)==set(port_order)
    replacement.append(f'.subckt {typ} {" ".join(logical_ports)}\nXphysical {" ".join(port_order)} {alias}\n.ends {typ}\n.subckt {alias} {" ".join(port_order)}\n{body}.ends {alias}\n')
    replacement.append(translated_model(args.temperature_c,aj,pj).replace('openpll_pw2nd_candidate','macro_reset_diode_fixed'))
    counts[typ]=11;resistor_counts[typ]=7
    for p in [args.diode_qualification.resolve(),diode_dir/'assessment.json',Path(__file__).with_name('diode_translation_probe_v2.py')]:pins[str(p)]=sha(p)
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
                  'cell_capacitors': counts, 'cell_resistors': resistor_counts, 'cell_topology_width_length_lvs_pass': True, 'diode_topology_area_perimeter_lvs_pass':True,
                  'diode_model_equivalence_screen_passed':True,'fixed_model_corner':args.corner,'fixed_model_temperature_c':args.temperature_c,
                  'wrong_width_control_rejected': True, 'mapped_cone_and_external_rc_unchanged': True,
                  'release_qualified': False, 'selected': False,
                  'limitations': ['Nominal Magic cellRC with 0.01 fF capacitance threshold; no cellRC process/temperature corners',
                                  'LVS does not compare junction area/perimeter; extracted GDS geometry is retained',
                                  'Diode translation fixed to selected primitive corner/temperature/geometry and tested biases; do not reuse outside this scope',
                                  'No expanded native cone, statistical metastability, supply noise, full reset network or whole-PLL proof']}
    (args.output / 'extraction.json').write_text(json.dumps(assessment, indent=2) + '\n')
    print(json.dumps({'cell_types': len(counts), 'explicit_cell_capacitors': sum(counts.values()),
                      'explicit_cell_resistors': sum(resistor_counts.values()),
                      'receiver_sha256': sha(target)}, indent=2))


if __name__ == '__main__':
    main()
