"""Compare antenna-check geometry with source GDS and independently count gate area."""
import argparse
from fractions import Fraction as F
import json
from math import gcd
import os
from pathlib import Path
import resource
import time

from common_v3 import save, sha, verify
from resources import identity, lease

MASKS = dict(poly=(66,20), diff=(65,20), tap=(65,44), nwell=(64,20),
             licon=(66,44), li1=(67,20), mcon=(67,44), met1=(68,20),
             via1=(68,44), met2=(69,20), via2=(69,44), met3=(70,20),
             via3=(70,44), met4=(71,20), via4=(71,44), met5=(72,20))


def run(source, control, output):
    output.mkdir(parents=True, exist_ok=False)
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(output/'status.json', dict(state='waiting_for_original_M5_geometry_control', release_ready=False))
    receipt = source/'assessment.json'; record = json.loads(receipt.read_text())
    verify(record['input_sha256']); verify(record['artifacts'])
    if not record['native_flat_layout_antenna_run_completed'] or record['residual_hierarchy_uses']:
        raise ValueError('completed full flattened antenna extraction required')
    candidates = [Path(p) for p in record['input_sha256'] if p.endswith('/assembly.gds')]
    if len(candidates) != 1:
        raise ValueError('one pinned source GDS required')
    original = candidates[0]; converted = source/'flat.gds'
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    owner=json.loads((control/'owner.json').read_text())
    while True:
        status=control/'status.json'
        state=json.loads(status.read_text())['state']
        if state=='M5_fill_alias_geometry_control_complete':break
        if state=='stopped_without_qualification' or identity(owner['pid'])!=str(owner['birth']):raise RuntimeError('original M5 alias control stopped')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original M5 control observation deadline; native workers unchanged')
        time.sleep(10)
    control_receipt=control/'assessment.json';c=json.loads(control_receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    techs=[Path(p) for p in record['input_sha256'] if p.endswith('/sky130A.tech')]
    if len(techs)!=1 or c['input_sha256'].get(str(techs[0]))!=record['input_sha256'][str(techs[0])]:raise ValueError('same actual pinned Magic technology required')
    if c.get('M5_drawing_plus_fill_roundtrip_preserved') is not True or c.get('drawing_only_comparison_fails_as_expected') is not True or c['source_purposes']!=[[72,20],[59,28],[72,99]]:raise ValueError('validated positive and negative M5 alias geometry control required')
    save(output/'status.json', dict(state='waiting_for_parent_geometry_resources', release_ready=False))
    with lease(1, 8, deadline):
        import pya
        save(output/'status.json', dict(state='parent_mask_union_comparison_running', release_ready=False))
        resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
        before = pya.Layout(); before.read(str(original))
        after = pya.Layout(); after.read(str(converted))
        if len(before.top_cells()) != 1 or len(after.top_cells()) != 1:
            raise ValueError('unique source/flat top cells required')
        units = [F(str(layout.dbu)) for layout in (before, after)]
        unit = F(gcd(units[0].numerator*units[1].denominator,
                     units[1].numerator*units[0].denominator),
                 units[0].denominator*units[1].denominator)
        regions = [{}, {}]; results = []
        for name, layer in MASKS.items():
            for index, layout in enumerate((before, after)):
                scale = units[index]/unit
                if scale.denominator != 1:
                    raise ValueError('exact integer common geometry grid required')
                region = pya.Region()
                purposes=[layer] if name!='met5' else [(72,20),(59,28),(72,99)]
                for purpose in purposes:
                    region += pya.Region(layout.top_cell().begin_shapes_rec(layout.layer(*purpose)))
                regions[index][name] = region.transformed(pya.ICplxTrans(int(scale), 0, False, 0, 0)).merged()
            a, b = regions[0][name], regions[1][name]
            difference = a ^ b
            results.append(dict(mask=name, GDS_layer=list(layer), exact_region_match=difference.is_empty(),
                source_area_um2=str(F(a.area())*unit**2), flat_area_um2=str(F(b.area())*unit**2),
                difference_area_um2=str(F(difference.area())*unit**2)))
        areas = [F((group['poly'] & group['diff']).area())*unit**2 for group in regions]
        if not all(area > 0 for area in areas):
            raise ValueError('transistor channel geometry absent')
        extracted = F(record['raw_gate_area_um2_at_1_over_200_grid'])
    detail = output/'geometry.json'; save(detail, results)
    inputs = [receipt, original, converted, control_receipt, techs[0], Path(__file__).resolve()]
    save(output/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
         artifacts={str(detail): sha(detail)}, common_geometry_grid_um=str(unit),
         all_checked_mask_regions_preserved=all(row['exact_region_match'] for row in results),
         M5_drawing_plus_fill_purposes=[[72,20],[59,28],[72,99]],
         M5_alias_normalization_independently_controlled=True,
         source_poly_diff_channel_area_um2=str(areas[0]), flat_poly_diff_channel_area_um2=str(areas[1]),
         raw_extracted_MOS_gate_area_um2=str(extracted),
         extracted_MOS_gate_area_matches_source_poly_diff_intersection=extracted==areas[0],
         source_and_flat_channel_areas_match=areas[0]==areas[1],
         antenna_engine_negative_controls_complete=False, parent_antenna_qualified=False, release_ready=False))
    save(output/'status.json', dict(state='controlled_parent_mask_geometry_compared', release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'control', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.source.resolve(), args.control.resolve(), args.output.resolve())
