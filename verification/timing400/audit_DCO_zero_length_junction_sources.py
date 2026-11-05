#!/usr/bin/env python3
"""Locate missing local junction attributes without adopting a junction model."""
from collections import Counter
import json
import math
import shlex
import signal
import time
import pya
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = base/'DCO_R_binding_trace_controls_001/trace'/(topname+'.ext')
    index = base/'DCO_original_device_geometry_ids_003/device_geometry_index.json'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    exporter = ROOT/'build/timing400/magic_location_source_001/ext2spice/ext2spice.c'
    pdk = __import__('pathlib').Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    instances = list(layout.top_cell().each_inst())
    gates = {}
    for inst in instances:
        if inst.cell.cell_index() not in gates:
            active = pya.Region(inst.cell.begin_shapes_rec(layout.layer(65, 20)))
            poly = pya.Region(inst.cell.begin_shapes_rec(layout.layer(66, 20)))
            gates[inst.cell.cell_index()] = active & poly
    cards = json.loads(index.read_text())
    keyed = {(r['model'], *r['rectangle_internal'][:2]): (name, r) for name, r in cards.items()}
    assert len(keyed) == 8620
    rows = []
    explicit = Counter()
    for line in ext.open():
        if not line.startswith('device msubckt '):
            continue
        f = shlex.split(line)
        model, x, y = f[2], int(f[3]), int(f[4])
        tail = f[-10:]
        for off in [4, 7]:
            if ',' in tail[off+2]:
                explicit[model] += 1
        if tail[5] != '0':
            assert ',' in tail[6]
            continue
        assert tail[6] == '0' and int(tail[8]) > 0 and ',' in tail[9]
        point = pya.Point(x*5, y*5)
        probe = pya.Region(pya.Box(x*5, y*5, x*5+5, y*5+5))
        hits = [i for i in instances if i.bbox().contains(point)
                and not (gates[i.cell.cell_index()].transformed(i.trans) & probe).is_empty()]
        assert len(hits) == 1
        inst = hits[0]
        assert inst.cell.name == 'sky130_fd_sc_hd__decap_3'
        name, card = keyed[model, x, y]
        params = dict(v.split('=', 1) for v in card['original_card'][5:])
        local_point = inst.trans.inverted()*point
        rows.append(dict(device=name, model=model, point_internal=[x, y],
            cell=inst.cell.name, instance_transform=str(inst.trans),
            point_in_cell_nm=[local_point.x, local_point.y],
            source_conductor=tail[4], source_boundary_length=0, source_attribute=tail[6],
            drain_boundary_length=int(tail[8]), drain_area_perimeter_attribute=tail[9],
            exported_source_area=params['as'], exported_source_perimeter=params['ps']))
    assert len(rows) == 152
    nonzero = [r for r in rows if float(r['exported_source_area']) != 0]
    assert len(nonzero) == 2
    assert {r['model'] for r in nonzero} == {r['model'] for r in rows}
    assert all(float(r['exported_source_perimeter'].lower().removesuffix('k')) > 0 for r in nonzero)
    source = exporter.read_text()
    body = source[source.index('spcnAPHier('):]
    assert 'if (!haveAttrs)' in body
    assert 'area = node->efnode_pa[resClass].pa_area;' in body
    assert 'perim = node->efnode_pa[resClass].pa_perim;' in body
    text = pdk.read_text()
    begin = text.index('.subckt sky130_fd_sc_hd__decap_3 ')
    cell = text[begin:text.index('.ends', begin)+5]
    assert 'X0 VPWR VGND VPWR VPB' in cell and 'X1 VGND VPWR VGND VNB' in cell
    out = base/'DCO_zero_length_junction_source_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'devices.json', rows)
    (out/'PDK_decap_3.spice').write_text(cell+'\n')
    inputs = [__import__('pathlib').Path(__file__).resolve(), owner, ext, index, gds, exporter, pdk]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in [out/'devices.json', out/'PDK_decap_3.spice']},
        zero_length_source_terminals=152, unique_decap_instances=len({r['instance_transform'] for r in rows}),
        zero_length_sources_all_in_actual_decap_3_GDS_instances=True,
        device_origin_box_overlaps_actual_poly_diffusion_gate_in_unique_instance=True,
        zero_length_sources_with_nonzero_exported_area_perimeter=nonzero,
        local_explicit_junction_terminal_counts=dict(explicit),
        exporter_missing_attribute_fallback_uses_entire_node_junction_area_perimeter=True,
        physical_junction_area_and_charge_qualified=False,
        interpretation='Two pre-R exported source junctions use global-node fallback rather than local source attributes. Do not blindly restore these as physical local junctions; independent diffusion geometry and charge validation remain required.',
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Located152 zero-length sources in76 actual decap instances; two nonzero global-fallback junction records remain physically unqualified.')


if __name__ == '__main__':
    main()
