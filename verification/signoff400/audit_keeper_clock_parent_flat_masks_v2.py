"""Compare completed ECO flat masks and electrically active selectors with source GDS."""
import argparse
import json
import os
from pathlib import Path
import time
from fractions import Fraction as F
from math import gcd
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from check_prototype_flat_antenna_geometry_v2 import MASKS
from audit_keeper_flat_geometry import DEVICE_MASKS
from check_keeper_active_selectors import domains


def run(output):
    import pya
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    flat = base / 'selected_keeper_clock_parent_flat_C_1482'
    receipt = flat / 'assessment.json'
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        owner = json.loads((flat / 'owner.json').read_text())
        save(output / 'status.json', dict(state='waiting_for_completed_flat_C_geometry', release_ready=False))
        while not receipt.exists():
            state = json.loads((flat / 'status.json').read_text())['state']
            if state == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
                raise RuntimeError('flat extraction stopped before completed geometry receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('geometry observation deadline')
            time.sleep(10)
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        control = base / 'selected_M5_fill_alias_control_555/assessment.json'
        c = json.loads(control.read_text())
        verify(c['input_sha256'])
        verify(c['artifacts'])
        sources = [Path(name) for name in a['input_sha256'] if name.endswith('/assembly.gds')]
        techs = [Path(name) for name in a['input_sha256'] if name.endswith('/sky130A.tech')]
        if (len(sources) != 1 or len(techs) != 1
                or c['input_sha256'].get(str(techs[0])) != a['input_sha256'][str(techs[0])]
                or not c['M5_drawing_plus_fill_roundtrip_preserved']
                or not c['drawing_only_comparison_fails_as_expected']):
            raise ValueError('source GDS and identical independently controlled M5 mapping required')
        layers = {**MASKS, **DEVICE_MASKS, 'diode': (81, 23)}
        files = [receipt, control, sources[0], flat / 'flat.gds', techs[0], Path(__file__).resolve(),
                 *[Path(__file__).with_name(name) for name in ('check_prototype_flat_antenna_geometry_v2.py',
                    'audit_keeper_flat_geometry.py', 'check_keeper_active_selectors.py')]]
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=8, release_ready=False))
        save(output / 'status.json', dict(state='comparing_closed_source_and_flat_masks', release_ready=False))
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            layouts = [pya.Layout(), pya.Layout()]
            for layout, path in zip(layouts, (sources[0], flat / 'flat.gds')):
                layout.read(str(path))
                if len(layout.top_cells()) != 1:
                    raise ValueError('unique geometry top required')
            if any(True for _ in layouts[1].top_cell().each_inst()):
                raise ValueError('flat geometry retains hierarchy')
            units = [F(str(layout.dbu)) for layout in layouts]
            unit = F(gcd(units[0].numerator * units[1].denominator,
                         units[1].numerator * units[0].denominator), units[0].denominator * units[1].denominator)
            regions = [{}, {}]
            rows = []
            for name, layer in layers.items():
                for i, layout in enumerate(layouts):
                    scale = units[i] / unit
                    if scale.denominator != 1:
                        raise ValueError('exact common geometry grid required')
                    region = pya.Region()
                    for purpose in ([layer] if name != 'met5' else [(72, 20), (59, 28), (72, 99)]):
                        index = layout.find_layer(*purpose)
                        if index is not None:
                            region += pya.Region(layout.top_cell().begin_shapes_rec(index))
                    regions[i][name] = region.transformed(pya.ICplxTrans(int(scale), 0, False, 0, 0)).merged()
                difference = regions[0][name] ^ regions[1][name]
                rows.append(dict(mask=name, region_match=difference.is_empty(),
                                 difference_area_um2=str(F(difference.area()) * unit**2)))
            before, after = regions
            d0, d1 = domains(before), domains(after)
            selectors = [dict(selector=name, active_domain_preserved=(((before[name] ^ after[name])
                         & (d0[name] | d1[name])).is_empty())) for name in d0]
            diode_match = ((before['diode'] & before['diff']) ^ (after['diode'] & after['diff'])).is_empty()
            channel_match = ((before['poly'] & before['diff']) ^ (after['poly'] & after['diff'])).is_empty()
        verify(pins)
        detail = output / 'masks.json'
        save(detail, dict(masks=rows, active_selectors=selectors))
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
             all_conductor_masks_preserved=all(row['region_match'] for row in rows if row['mask'] in MASKS),
             all_device_select_masks_preserved=all(row['region_match'] for row in rows if row['mask'] in DEVICE_MASKS),
             all_checked_active_selectors_preserved=all(row['active_domain_preserved'] for row in selectors),
             diode_marker_on_active_diff_preserved=diode_match, poly_diff_channel_region_preserved=channel_match,
             M5_alias_control_verified=True, capacitance_coefficient_equivalence_qualified=False,
             flat_GDS_is_not_a_fabrication_replacement=True, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='ECO_flat_mask_comparison_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
