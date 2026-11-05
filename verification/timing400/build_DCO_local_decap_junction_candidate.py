#!/usr/bin/env python3
"""Correct decap junction geometry in metadata, without runtime model adoption."""
from collections import defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import shlex
import signal
import time
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    diagnostic = base/'DCO_zero_length_junction_source_audit_001/assessment.json'
    assert verify(diagnostic)['device_origin_box_overlaps_actual_poly_diffusion_gate_in_unique_instance']
    proof = base/'DCO_private_R_primitives_001/assessment.json'
    assert verify(proof)['every_native_R_branch_multiplicity_and_value_recovered']
    records = json.loads((diagnostic.parent/'devices.json').read_text())
    devices = json.loads((proof.parent/'device_connections.json').read_text())
    nodes = {r['private_id']: r for r in json.loads((proof.parent/'nodes.json').read_text())}
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = base/'DCO_R_binding_trace_controls_001/trace'/(topname+'.ext')
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    cell = layout.cell('sky130_fd_sc_hd__decap_3')
    active = pya.Region(cell.begin_shapes_rec(layout.layer(65, 20)))
    poly = pya.Region(cell.begin_shapes_rec(layout.layer(66, 20)))
    diffusion = list((active-poly).each_merged())
    assert len(diffusion) == 4
    instances = {str(i.trans): i for i in layout.top_cell().each_inst() if i.cell.name == cell.name}
    totals = defaultdict(lambda: [0, 0])
    local_rows = []
    for r in records:
        d = devices[r['device']]
        inst = instances[r['instance_transform']]
        endpoints = {}
        for code in [2, 3]:
            private = d['private_terminals'][d['native_terminal_codes'].index(code)]
            n = nodes[private]
            assert n['original_conductor'] == r['source_conductor']
            x, y = n['point_internal']
            local = inst.trans.inverted()*pya.Point(x*5, y*5)
            probe = pya.Region(pya.Box(local.x-1, local.y-1, local.x+1, local.y+1))
            hits = [p for p in diffusion if not (pya.Region(p) & probe).is_empty()]
            assert len(hits) == 1, (r['device'], code, str(local), len(hits))
            polygon = hits[0]
            assert polygon.area() % 25 == 0 and polygon.perimeter() % 5 == 0
            endpoints[code] = dict(private_node=private, local_polygon_nm=polygon.to_s(),
                area_internal=polygon.area()//25, perimeter_internal=polygon.perimeter()//5,
                area_um2=str(Decimal(polygon.area())/1000000),
                perimeter_um=str(Decimal(polygon.perimeter())/1000))
        assert endpoints[2]['local_polygon_nm'] != endpoints[3]['local_polygon_nm']
        assert (endpoints[2]['area_internal'], endpoints[2]['perimeter_internal']) == (
            endpoints[3]['area_internal'], endpoints[3]['perimeter_internal'])
        assert r['drain_area_perimeter_attribute'] == '%s,%s' % (
            endpoints[3]['area_internal'], endpoints[3]['perimeter_internal'])
        params = dict(v.split('=', 1) for v in d['original_card'][5:])
        assert Decimal(params['ad']) == Decimal(endpoints[3]['area_um2'])
        assert Decimal(params['pd']) == Decimal(endpoints[3]['perimeter_um'])
        corrected = list(d['original_card'])
        corrected[5:] = [
            'as='+endpoints[2]['area_um2'] if v.startswith('as=') else
            'ps='+endpoints[2]['perimeter_um'] if v.startswith('ps=') else v
            for v in corrected[5:]]
        d['junction_corrected_candidate_card'] = corrected
        d['junction_candidate_basis'] = 'independent_actual_GDS_diffusion_polygon_at_each_private_S_D_boundary'
        d['junction_distribution_qualified'] = False
        for index, value in enumerate([endpoints[2]['area_internal'], endpoints[2]['perimeter_internal']]):
            totals[r['model']][index] += value
        local_rows.append(dict(device=r['device'], model=r['model'], source=endpoints[2], drain=endpoints[3]))
    # Compare explicit local A/P plus independently recovered missing sides with
    # exact integer native node inventory, before SPICE print rounding.
    explicit = defaultdict(lambda: [0, 0])
    inventory = {}
    for line in ext.open():
        if line.startswith('node "VPWR"') or line.startswith('substrate "VGND"'):
            f = shlex.split(line)
            inventory[f[1]] = list(zip(map(int, f[7::2]), map(int, f[8::2])))
        if not line.startswith('device msubckt '):
            continue
        f = shlex.split(line)
        tail = f[-10:]
        rail = 'VGND' if f[2] == 'sky130_fd_pr__nfet_01v8' else 'VPWR'
        for off in [4, 7]:
            if tail[off] == rail and ',' in tail[off+2]:
                for index, value in enumerate(map(int, tail[off+2].split(','))):
                    explicit[f[2]][index] += value
    balance = []
    for model, rail, rc in [('sky130_fd_pr__nfet_01v8', 'VGND', 4),
                            ('sky130_fd_pr__pfet_01v8_hvt', 'VPWR', 5)]:
        native = inventory[rail][rc]
        corrected = tuple(a+b for a, b in zip(explicit[model], totals[model]))
        assert corrected == native
        # Both legacy choices are rejected: retaining global fallback duplicates
        # local inventory; dropping it with no local repair loses physical sides.
        assert tuple(explicit[model]) != native
        legacy = tuple(a+b for a, b in zip(explicit[model], native))
        assert legacy != native
        balance.append(dict(model=model, rail=rail, native_resistance_class=rc,
            native_node_area_perimeter=list(native), explicit_area_perimeter=explicit[model],
            recovered_missing_area_perimeter=totals[model], corrected_area_perimeter=list(corrected),
            pre_R_global_fallback_plus_explicit_area_perimeter=list(legacy)))
    assert len(local_rows) == 152 and len(devices) == 8620
    out = base/'DCO_local_decap_junction_candidate_001'
    out.mkdir(exist_ok=False)
    save(out/'local_junction_regions.json', local_rows)
    save(out/'device_connections_candidate.json', devices)
    save(out/'native_area_perimeter_balance.json', balance)
    inputs = [Path(__file__).resolve(), owner, diagnostic, proof, ext, gds,
        diagnostic.parent/'devices.json', proof.parent/'nodes.json', proof.parent/'device_connections.json']
    artifacts = [out/'local_junction_regions.json', out/'device_connections_candidate.json', out/'native_area_perimeter_balance.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts},
        source_junction_candidates_corrected=152, unique_decap_instances=76,
        physical_diffusion_regions_match_private_source_and_drain_boundary_points=True,
        existing_local_drain_area_perimeter_match_independent_GDS=True,
        corrected_rail_junction_area_perimeter_exactly_matches_native_inventory=True,
        original_global_fallback_double_count_and_post_R_missing_side_controls_rejected=True,
        all_other_device_parameters_and_connections_preserved=True,
        nonlinear_junction_charge_and_spatial_integration_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Recovered152 local source junction regions; both rail A/P totals now exactly match native inventory. Candidate metadata only.')


if __name__ == '__main__':
    main()
