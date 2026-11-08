"""Compare rectangular port projection while keeping RC conservation explicit."""
import argparse
import json
import re
from decimal import Decimal
from pathlib import Path
from common_v3 import save, sha, verify
from compare_magic_area_signfix import events, signature
from audit_keeper_native_R_contraction import compare


def fixture_C_reference(ext):
    """C-only view of these flat, device-free, capscale-one native fixtures."""
    ports = []
    caps = []
    substrate = None
    nodes = []
    coupling = []
    for line in ext.read_text().splitlines():
        if line.startswith('scale ') and line.split()[2] != '1':
            raise ValueError('fixture capscale one required')
        if line.startswith(('use ', 'device ', 'fet ')):
            raise ValueError('flat device-free fixture required')
        if line.startswith('port '):
            m = re.match(r'port "(\w+)" (\d+) ', line)
            if not m:
                raise ValueError('simple fixture port required')
            ports.append((int(m[2]), m[1]))
        elif line.startswith('substrate '):
            m = re.match(r'substrate "(\w+)" ', line)
            if not m or substrate is not None:
                raise ValueError('one fixture substrate required')
            substrate = m[1]
        elif line.startswith('node '):
            m = re.match(r'node "(\w+)" \S+ (\S+) ', line)
            if not m:
                raise ValueError('simple fixture node required')
            nodes.append((m[1], Decimal(m[2])))
        elif line.startswith('cap '):
            m = re.fullmatch(r'cap "(\w+)" "(\w+)" (\S+)', line)
            if not m:
                raise ValueError('simple fixture coupling required')
            coupling.append((m[1], m[2], Decimal(m[3])))
    if substrate is None or not ports:
        raise ValueError('complete fixture node records required')
    caps.extend((n, substrate, value) for n, value in nodes)
    caps.extend(coupling)
    text = '.subckt fixture ' + ' '.join(n for _, n in sorted(ports)) + '\n'
    for index, (a, b, value) in enumerate(caps):
        text += f'Cref{index} {a} {b} {value / Decimal(10**18)}\n'
    return text + '.ends\n'


def run(baseline_local, baseline_broad, candidate_local, candidate_broad,
        baseline_engine, engine, output):
    roots = [baseline_local, baseline_broad, candidate_local, candidate_broad]
    receipts = [p / 'assessment.json' for p in [*roots, baseline_engine, engine]]
    a, b, c, d, old, new = [json.loads(p.read_text()) for p in receipts]
    for r in (a, b, c, d, old, new):
        verify(r['input_sha256'])
        verify(r['artifacts'])
    if old.get('port_drivepoint_tile_intersection_corrected', False) or new.get('port_drivepoint_tile_intersection_corrected') is not True:
        raise ValueError('unprojected baseline and projected candidate required')
    if not old['single_breakpoint_area_sign_corrected'] or not new['single_breakpoint_area_sign_corrected'] or not new['rectilinear_port_projection_only']:
        raise ValueError('matching sign correction and rectangular projection scope required')
    for r, receipt in [(a, receipts[4]), (b, receipts[4]), (c, receipts[5]), (d, receipts[5])]:
        if r['input_sha256'].get(str(receipt)) != sha(receipt):
            raise ValueError('active engine identity mismatch')
    if not a['all_six_native_controls_complete'] or not c['all_six_native_controls_complete'] or not b['all_two_native_controls_complete'] or not d['all_two_native_controls_complete']:
        raise ValueError('completed native controls required')
    metadata = [p / 'instrumentation.json' for p in (baseline_engine, engine)]
    left, right = [json.loads(p.read_text()) for p in metadata]
    changed_files = [n for n in left['instrumented_source_sha256']
                     if left['instrumented_source_sha256'][n] != right['instrumented_source_sha256'][n]]
    if changed_files != ['resis.h'] or left['header_sha256'] != right['header_sha256']:
        raise ValueError('only NEWPORT-containing source header may differ')
    pins = {str(p): sha(p) for p in [*receipts, *metadata, Path(__file__).resolve(),
                                    Path(__file__).with_name('compare_magic_area_signfix.py'),
                                    Path(__file__).with_name('probe_magic_resistance_area_trace.py'),
                                    Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
    cases = [(baseline_local, candidate_local, n, False) for n in ('horizontal', 'vertical', 'dangling_tee')]
    cases.append((baseline_broad, candidate_broad, 'dangling_tee', True))
    results = []
    all_checks = []
    manifests = {baseline_local: a, baseline_broad: b, candidate_local: c, candidate_broad: d}
    for before, after, name, broad in cases:
        x, y = before / (name + '_on'), after / (name + '_on')
        ext_name = 'Area_' + name + '.ext'
        for root, folder in ((before, x), (after, y)):
            m = manifests[root]
            closure = {**m['input_sha256'], **m['artifacts']}
            for filename in ('probe.tcl', 'view.spice', 'area.jsonl', ext_name):
                path = folder / filename
                if closure.get(str(path)) != sha(path):
                    raise ValueError('fixture artifact identity mismatch')
                pins[str(path)] = closure[str(path)]
        protocol = (x / 'probe.tcl').read_text().replace(str(x), '<CASE>') == (y / 'probe.tcl').read_text().replace(str(y), '<CASE>')
        ext_match = sorted((x / ext_name).read_text().splitlines()) == sorted((y / ext_name).read_text().splitlines())
        sx, sy = signature((x / 'view.spice').read_text()), signature((y / 'view.spice').read_text())
        ry = events(y / 'area.jsonl')
        raw = [r for r in ry if r['kind'] == 'raw_resistance_area']
        invalid = []
        for r in raw:
            box, tile = r['support_box'], r['tile_box']
            if not (tile[0] <= box[0] <= box[2] <= tile[2] and tile[1] <= box[1] <= box[3] <= tile[3]):
                invalid.append(r)
        negative_raw = sum(float.fromhex(r['native_added_hex']) < 0 for r in raw)
        negative_C = sum(n for (_, value), n in sy[2].items() if value < 0)
        checks = [protocol, ext_match, sx[0] == sy[0], sx[1] == sy[1], not invalid, not negative_raw, not negative_C]
        if not broad:
            checks.append(sx == sy)
        conservation = compare(fixture_C_reference(y / ext_name), (y / 'view.spice').read_text())
        detail = dict(case=name, port_scope='broad' if broad else 'localized',
                      electrical_protocol_matches=protocol, C_only_EXT_inventory_unchanged=ext_match,
                      exact_final_circuit_unchanged=sx == sy,
                      baseline_R_cards=sum(sx[3].values()), candidate_R_cards=sum(sy[3].values()),
                      candidate_invalid_support_bounds=len(invalid), candidate_negative_raw_additions=negative_raw,
                      candidate_negative_C_cards=negative_C, C_only_reference_contraction=conservation,
                      port_projection_fixture_checks_passed=all(checks))
        results.append(detail)
        all_checks.extend(checks)
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'assessment.json', dict(input_sha256=pins, differing_transformed_source_files=changed_files,
                                          results=results, all_port_projection_fixture_checks_passed=all(all_checks),
                                          split_tile_projection_qualified=False, coupling_duplication_fixed=False,
                                          distributed_wire_R_qualified=False, release_ready=False))
    if not all(all_checks):
        raise ValueError('port projection comparison failed; receipt retained')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    names = ('baseline_local', 'baseline_broad', 'candidate_local', 'candidate_broad', 'baseline_engine', 'engine', 'output')
    for n in names:
        p.add_argument('--' + n.replace('_', '-'), type=Path, required=True)
    a = p.parse_args()
    run(*(getattr(a, n).resolve() for n in names))
