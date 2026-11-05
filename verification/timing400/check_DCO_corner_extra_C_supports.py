#!/usr/bin/env python3
"""Check min/max-only diffusion support boxes against independent actual GDS."""
import json
import math
from pathlib import Path
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
    comparison = base/'DCO_RC_corner_endpoint_support_comparison_001/assessment.json'
    compared = verify(comparison)
    nominal = base/'DCO_all_C_endpoint_GDS_identity_001/assessment.json'
    assert verify(nominal)['all_nominal_endpoint_samples_on_expected_GDS_layer_conductor_or_well']
    registry_path = base/'DCO_GDS_conductor_registry_001/conductor_registry.json'
    registry = json.loads(registry_path.read_text())
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    engine, regs = engine_at_stage(conductor_geometry(layout, top), 'm5')
    nw = pya.Region(top.begin_shapes_rec(layout.layer(64, 20))).merged()
    results = []
    inputs = [Path(__file__).resolve(), owner, comparison, nominal, registry_path, gds,
        Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    for corner in ['min', 'max']:
        path = comparison.parent/(corner+'_extra_endpoints.json')
        inputs.append(path)
        extras = json.loads(path.read_text())
        assert len(extras) == next(r['unique_extra_supports'] for r in compared['results'] if r['corner'] == corner)
        for key in extras:
            name, plane, material, raw, *box = key
            assert plane == 'active' and material in ['ndiff', 'pdiff']
            l, b, r, t = [v*5 for v in box]
            support = pya.Region(pya.Box(l, b, r, t))
            assert support.area() > 0
            expected = registry[name]['GDS_clusters']
            hits = []
            for x, y in [(l+1, b+1), (r-1, t-1), ((l+r)//2, (b+t)//2)]:
                net = engine.probe_net(regs['diff'], pya.Point(x, y))
                assert net is not None and [net.cluster_id] == expected, (key, x, y)
                actual = engine.shapes_of_net(net, regs['diff'], True).merged()
                assert (support-actual).is_empty()
                hits.append(dict(point_nm=[x, y], cluster=net.cluster_id))
            assert (support-nw).is_empty() if material == 'pdiff' else (support & nw).is_empty()
            results.append(dict(corner=corner, original_conductor=name, effective_material=material,
                box_internal=box, GDS_probes=hits, complete_diffusion_box_on_expected_conductor_and_well=True))
    out = base/'DCO_corner_extra_C_support_geometry_001'
    out.mkdir(exist_ok=False)
    save(out/'supports.json', results)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(out/'supports.json'): sha(out/'supports.json')},
        min_extra_supports_checked=5, max_extra_supports_checked=10,
        all_corner_extra_support_boxes_on_expected_GDS_diffusion_conductor_and_well=True,
        full_min_max_endpoint_sets_covered_by_nominal_sampled_geometry_plus_extra_box_checks=True,
        coefficient_weights_implicit_ground_distribution_and_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Checked all5 minimum and10 maximum RC-only endpoint boxes against actual GDS conductor/well geometry.')


if __name__ == '__main__':
    main()
