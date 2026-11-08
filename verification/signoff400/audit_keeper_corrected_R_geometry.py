"""Audit completed PLL R geometry without promoting a nonconserving RC model."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify
from audit_keeper_native_R_contraction import compare
from audit_magic_resistance_lineage_v2 import audit as lineage_audit
from audit_magic_resistance_area_v2 import audit as area_audit
from extract_keeper_flat_geometry_C import FLAT


def run(flat, pilot, output):
    receipts = [p / 'assessment.json' for p in (flat, pilot)]
    a, b = [json.loads(p.read_text()) for p in receipts]
    closure = {}
    for r in (a, b):
        for key, value in {**r['input_sha256'], **r['artifacts']}.items():
            if key in closure and closure[key] != value:
                raise ValueError('conflicting native identity pins')
            closure[key] = value
    verify(closure)
    if not b['native_process_completed'] or b['requested_net'] != 'PLLOUT':
        raise ValueError('completed PLLOUT-only pilot required')
    if not b['single_breakpoint_area_sign_corrected'] or not b['port_drivepoint_tile_intersection_corrected']:
        raise ValueError('explicit corrected geometry identity required')
    if b['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('same checked flat source required')
    if b['native_statistics']['extracted_nets'] != [1] or b['native_statistics']['output_nets'] != [1]:
        raise ValueError('one extracted and exported resistance net required')
    source, candidate = flat / 'capacitance.spice', pilot / 'pilot.spice'
    trace, res_ext = pilot / 'resistance_area.jsonl', pilot / (FLAT + '.res.ext')
    helpers = ['audit_keeper_native_R_contraction.py', 'audit_magic_resistance_lineage_v2.py',
               'audit_magic_resistance_area.py', 'audit_magic_resistance_area_v2.py', 'native_spice_comments.py']
    pins = {str(p): sha(p) for p in [*receipts, source, candidate, trace, res_ext, Path(__file__).resolve(),
                                    *[Path(__file__).with_name(n) for n in helpers]]}
    output.mkdir(parents=True, exist_ok=False)
    metrics = compare(source.read_text(), candidate.read_text())
    lineage = lineage_audit(trace, res_ext)
    raw = output / 'raw_area_events.jsonl'
    with trace.open() as stream, raw.open('w') as target:
        for line in stream:
            if json.loads(line)['kind'] == 'raw_resistance_area':
                target.write(line)
    areas = area_audit(raw)
    if areas['raw_area_events'] != lineage['raw_area_updates']:
        raise ValueError('complete raw-area lineage coverage required')
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256={**closure, **pins},
                                          artifacts={str(raw): sha(raw)},
                                          contraction=metrics, numerical_lineage=lineage, raw_area_support=areas,
                                          primitive_and_port_contraction_preserved=metrics['primitive_multisets_match'] and metrics['ordered_formal_ports_match'] and not metrics['components_joining_distinct_reference_nodes'],
                                          capacitance_conservation_verified=metrics['exact_aggregated_C_match'],
                                          spatial_capacitance_placement_qualified=False,
                                          distributed_wire_R_qualified=False, native_simulation_allowed=False,
                                          release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('flat', 'pilot', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.flat.resolve(), a.pilot.resolve(), a.output.resolve())
