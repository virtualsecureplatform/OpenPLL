#!/usr/bin/env python3
"""Identify coarse support metadata that cannot define local C charge kernels."""
from fractions import Fraction
import json
from pathlib import Path
import time
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < json.loads(owner.read_text())['deadline_uptime']
    src = ROOT/'build/timing400/magic_location_source_001/extract'
    basic, couple = (src/'ExtBasic.c').read_text(), (src/'ExtCouple.c').read_text()
    body = basic[basic.index('OpenPLLTraceGroundTile('):basic.index('OpenPLLTracePair(')]
    assert 'TITORECT(tile, &support);' in body
    assert basic.count('OpenPLLTraceGroundTile(reg, reg->nreg_cap - openpll_before, tile, "tile_perimeter"') == 5
    assert couple.count('TITORECT(tp, &openpll_target);') == 2
    assert 'TITORECT(tp, &sov.so_clip);' in couple
    assert 'GEOCLIP(&sov.so_clip, esws->area);' in couple
    assert 'length = sov.so_clip.r_ytop - sov.so_clip.r_ybot;' in couple
    assert 'sfar = 0.6366 * atan(mult * dfar);' in couple
    survey = base/'DCO_unresolved_C_surface_survey_001/supports.json'
    rows = json.loads(survey.read_text())
    example = None
    for row in rows:
        for native in row['native_examples']:
            f = native['contribution'].split()
            if f[0] != 'OPENPLL_P' or f[4] != 'edge_fringe':
                continue
            a, b = list(map(int, f[6:10])), list(map(int, f[10:14]))
            if a[0] == a[2] and b[1] < a[1] < a[3] < b[3]:
                fraction = Fraction((b[3]-b[1])-(a[3]-a[1]), b[3]-b[1])
                if fraction > Fraction(99, 100):
                    example = dict(native_example=native, source_edge_box_internal=a,
                        complete_target_tile_box_internal=b,
                        fraction_of_uniform_target_box_charge_outside_native_longitudinal_projection=str(fraction))
                    break
        if example:
            break
    assert example is not None
    comparison = base/'DCO_C_surface_trace_controls_001/comparison.json'
    nom = next(r for r in json.loads(comparison.read_text()) if r['corner'] == 'nom')
    assert nom['events_by_reason']['tile_perimeter'] == 309861
    assert nom['events_by_reason']['edge_fringe'] == 3460669
    out = base/'DCO_C_charge_kernel_metadata_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'coarse_box_counterexample.json', example)
    requests = dict(
        tile_area='Retain exact area/triangle support and any nonuniform density exclusions.',
        tile_perimeter='Retain actual clipped edge interval, direction and per-edge density; whole tile bounds do not identify the contributing edge.',
        overlap='Retain actual overlap integration patches and recursive shield exclusions, including fractional split-tile support.',
        edge_fringe='Retain source projected interval, clipped target rectangle, direction, near/far distances, atan multiplier and recursive shield-kernel pieces.',
        ground_fringe_corrections='Retain the corresponding projected source intervals/shield pieces and roundoff residual separately from physical charge.',
        sidewall='Audit exact paired edge intervals and distance law before assigning voltage weights.')
    save(out/'required_kernel_fields.json', requests)
    paths = [Path(__file__).resolve(), owner, src/'ExtBasic.c', src/'ExtCouple.c', survey, comparison]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in [out/'coarse_box_counterexample.json', out/'required_kernel_fields.json']},
        nominal_contribution_counts_by_reason=nom['events_by_reason'],
        whole_tile_perimeter_boxes_do_not_identify_local_edges=True,
        fringe_target_tile_bounds_exceed_native_clipped_integration_support=True,
        uniform_target_box_C_weights_rejected_by_actual_native_counterexample=True,
        existing_matrix_accounting_and_sampled_geometry_controls_invalidated=False,
        local_charge_kernel_metadata_complete=False, C_contribution_weights_emitted=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Charge-kernel metadata gap confirmed: perimeter edges and clipped fringe/shield integrals must be retained before C weights.')


if __name__ == '__main__':
    main()
