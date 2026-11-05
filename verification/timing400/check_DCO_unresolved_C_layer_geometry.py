#!/usr/bin/env python3
"""Check unresolved C supports on their actual metal layer and mesh contacts.

Same-metal-island correspondence identifies a candidate voltage representation;
it does not qualify uniform island potential or capacitor integration weights.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shlex
import signal
import time
import pya
from check_compact_clock_tree import verify
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    survey = base/'DCO_unresolved_C_surface_survey_001/assessment.json'
    assert verify(survey)['all_targets_recovered_with_exact_serial_alignment']
    source = survey.parent/'supports.json'
    rows = json.loads(source.read_text())
    binding = base/'DCO_private_R_primitives_001'
    nodes = json.loads((binding/'nodes.json').read_text())
    by_id = {r['private_id']: r for r in nodes}
    types = {}
    provenance = base/'DCO_R_binding_trace_controls_001/trace/R_provenance.log'
    for line in provenance.open():
        if line.startswith('TYPE '):
            f = shlex.split(line)
            types[int(f[1])] = f[2]
        elif line.startswith('BEGIN '):
            break
    planes = {f'metal{i}': {f'm{i}'} for i in range(1, 6)}
    planes.update(locali={'li'}, poly={'poly'}, viali={'li', 'm1'},
                  via1={'m1', 'm2'}, via2={'m2', 'm3'}, via3={'m3', 'm4'}, via4={'m4', 'm5'})
    incident = defaultdict(list)
    with (binding/'branches.jsonl').open() as stream:
        for line in stream:
            r = json.loads(line)
            material = types[int(r['material_type_id'])]
            for node in r['private_nodes']:
                incident[node].append(material)
    native_layer = {}
    for node, materials in incident.items():
        known = [planes[m] for m in materials if m in planes]
        if known:
            common = set.intersection(*known)
            if len(common) == 1:
                native_layer[node] = next(iter(common))
    candidates = defaultdict(list)
    for node, layer in native_layer.items():
        r = by_id[node]
        candidates[r['original_conductor'], layer].append(r)
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    engine, regs = engine_at_stage(conductor_geometry(layout, top), 'm5')
    terminal_path = base/'DCO_intercell_wire_rc_geometry_001/terminals.json'
    labels = {}
    for r in json.loads(terminal_path.read_text()):
        if r['logical_net'] is not None:
            assert len(r['clusters']) == 1
            labels[r['logical_net']] = r['clusters'][0]
    results, counts = [], Counter()
    for row in rows:
        layers = {g['plane'].replace('metal', 'm') for g in row['surface_groups']}
        assert len(layers) == 1
        layer = next(iter(layers))
        l, b, r, t = [v*5 for v in row['box_internal']]
        probe = pya.Region(pya.Box(l-1, b-1, r+1, t+1))
        islands = list(regs[layer].interacting(probe).each_merged())
        assert len(islands) == 1, (row['original_conductor'], row['box_internal'], len(islands))
        island = pya.Region(islands[0])
        hits = []
        for x, y in {(l, b), (r, t), ((l+r)//2, (b+t)//2)}:
            found = []
            for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                net = engine.probe_net(regs[layer], pya.Point(x+dx, y+dy))
                if net is not None:
                    found.append(net.cluster_id)
            assert labels[row['original_conductor']] in found
            hits.append(dict(point_nm=[x, y], clusters=sorted(set(found))))
        voltage_candidates = []
        for node in candidates[row['original_conductor'], layer]:
            x, y = [v*5 for v in node['point_internal']]
            if not (island & pya.Region(pya.Box(x-1, y-1, x+1, y+1))).is_empty():
                voltage_candidates.append(dict(private_id=node['private_id'], point_internal=node['point_internal'],
                    incident_native_materials=sorted(set(incident[node['private_id']]))))
        # Layer metadata independently filters the four old single-tile ambiguities.
        prior = []
        for tile in row['example_tiles']:
            if planes.get(types[int(tile['type_id'])]) == {layer}:
                prior.append(tile['private_id'])
        state = ('one_correct_layer_single_tile' if len(prior) == 1 else
                 'one_same_metal_island_mesh_vertex' if len(voltage_candidates) == 1 else
                 'multiple_same_metal_island_mesh_vertices' if voltage_candidates else
                 'no_layer_identified_mesh_vertex_on_island')
        counts[state] += 1
        results.append(dict(**row, actual_GDS_layer=layer, layer_probes=hits,
            actual_metal_island_nm=islands[0].to_s(), same_layer_prior_single_tile_candidates=prior,
            same_metal_island_private_mesh_vertices=voltage_candidates, geometry_classification=state))
    out = base/'DCO_unresolved_C_layer_geometry_001'
    out.mkdir(exist_ok=False)
    save(out/'supports.json', results)
    inputs = [Path(__file__).resolve(), owner, survey, source, gds, provenance, terminal_path,
        binding/'nodes.json', binding/'branches.jsonl',
        Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(out/'supports.json'): sha(out/'supports.json')}, checked_signal_supports=len(rows),
        actual_GDS_expected_net_on_recorded_metal_layer_all_probes_passed=True,
        geometry_classifications=dict(counts), uniform_island_potential_or_RC_error_qualified=False,
        capacitor_weights_or_attachment_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    print('Layer-aware301 support geometry:', dict(counts))


if __name__ == '__main__':
    main()
