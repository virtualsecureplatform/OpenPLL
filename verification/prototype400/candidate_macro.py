"""Resolve a digital macro only through matching current-source CAD receipts."""
import json
from pathlib import Path
from common import source_pins, sha, verify


def digital_views(route, checks, placement):
    route, checks, placement = map(lambda p: Path(p).resolve(), (route, checks, placement))
    evidence = {}
    def read(path):
        path = Path(path).resolve()
        evidence[str(path)] = sha(path)
        return json.loads(path.read_text())
    placed_path = placement / 'assessment.json'
    placed = read(placed_path)
    verify(placed['input_sha256']); verify(placed['artifacts'])
    if not placed.get('placement_completed') or any(
            placed['input_sha256'].get(path) != digest for path, digest in source_pins().items()):
        raise ValueError('digital placement does not match current candidate source')
    # Follow only pinned assessment dependencies, permitting an intervening
    # antenna-repair stage while rejecting an unrelated placement selection.
    visited = set()
    def ancestry(path):
        path = Path(path).resolve()
        if path in visited:
            return False
        if len(visited) >= 64:
            raise ValueError('excessive CAD receipt ancestry')
        visited.add(path)
        report = read(path)
        # Layout/model side receipts can have another schema. They are
        # still hash-pinned by their parent, but do not form CAD ancestry.
        if not isinstance(report.get('input_sha256'),dict) or not isinstance(report.get('artifacts'),dict):
            return False
        verify(report['input_sha256']); verify(report['artifacts'])
        if path == placed_path:
            return True
        for child, digest in report['input_sha256'].items():
            child = Path(child).resolve()
            if child.name == 'assessment.json':
                if sha(child) != digest:
                    raise ValueError('CAD receipt ancestry hash mismatch')
                if ancestry(child):
                    return True
        return False
    routed = read(route / 'assessment.json')
    if not routed.get('digital_routing_completed') or not routed.get('nominal_rc_extracted'):
        raise ValueError('digital route is incomplete')
    if not ancestry(route / 'assessment.json'):
        raise ValueError('digital route does not descend from selected placement')
    checked = read(checks / 'assessment.json')
    if not checked.get('digital_layout_pass'):
        raise ValueError('digital independent layout checks have not passed')
    layout_path = Path(checked['digital_layout_assessment']).resolve()
    if layout_path != route / 'signoff/assessment.json':
        raise ValueError('layout checks belong to another digital route')
    for key in ('route_equivalence', 'digital_layout_assessment'):
        if sha(checked[key]) != checked[key + '_sha256']:
            raise ValueError('digital check receipt hash mismatch')
    equivalent = read(checked['route_equivalence'])
    verify(equivalent['input_sha256']); verify(equivalent['artifacts'])
    if (not equivalent.get('all_transition_and_output_functions_equivalent') or
            not equivalent.get('corrupted_reset_function_rejected') or
            equivalent['input_sha256'].get(str(route / 'route.v')) != sha(route / 'route.v')):
        raise ValueError('equivalence does not cover selected digital route')
    layout = read(layout_path)
    verify(layout['sha256'])
    gds, lef = route / 'signoff/route.gds', route / 'digital.lef'
    if (not layout.get('diagnostic_physical_pass') or
            layout['sha256'].get(str(gds)) != sha(gds) or
            layout['sha256'].get(str(route / 'route.odb')) != sha(route / 'route.odb') or
            routed['artifacts'].get(str(lef)) != sha(lef)):
        raise ValueError('digital GDS/LEF/database identity is not covered')
    return dict(lef=str(lef), gds=str(gds), master='IntegerPLL_ProgrammedCore',
                route=str(route), placement=str(placement), checks=str(checks),
                evidence_sha256=evidence)
