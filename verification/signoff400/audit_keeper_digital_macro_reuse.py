"""Bind historical internal digital STA geometry to the current parent macro."""
import argparse
from collections import Counter
import json
import os
import sys
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease


def compare_cells(left, right, master):
    import pya
    a, b = left.cell(master), right.cell(master)
    if a is None or b is None or left.dbu != right.dbu:
        raise ValueError('same named macro and geometry grid required')
    layers = sorted({(i.layer, i.datatype) for layout in [left, right] for i in layout.layer_infos()})
    rows = []
    for layer, datatype in layers:
        regions, labels = [], []
        for layout, cell in [(left, a), (right, b)]:
            index = layout.find_layer(layer, datatype)
            if index is None:
                regions.append(pya.Region())
                labels.append(Counter())
            else:
                regions.append(pya.Region(cell.begin_shapes_rec(index)))
                texts = Counter()
                for item in cell.begin_shapes_rec(index).each():
                    if item.shape().is_text():
                        texts[item.shape().text.transformed(item.trans()).to_s()] += 1
                labels.append(texts)
        difference = regions[0] ^ regions[1]
        rows.append(dict(layer=layer, datatype=datatype, polygon_XOR_empty=difference.is_empty(), polygon_XOR_area_dbu2=difference.area(), recursive_texts_match=labels[0] == labels[1]))
    return dict(master=master, dbu_um=left.dbu, layers=rows, all_recursive_layer_geometry_and_texts_match=all(r['polygon_XOR_empty'] and r['recursive_texts_match'] for r in rows))


def run(output):
    import pya
    import klayout.dbcore
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {29})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    route = b / 'prototype_v3_selected_route_019/route.odb'
    source = b / 'prototype_v3_selected_route_019/signoff/route.gds'
    signoff = b / 'prototype_v3_selected_route_019/signoff/assessment.json'
    current = b / 'selected_keeper_checked_filled_parent_1147/assembly.gds'
    current_receipt = current.parent / 'assessment.json'
    screens = [b / ('prototype_v3_selected_402p1_timing_' + c + '_019/assessment.json') for c in ['tt', 'ff', 'ss', 'sf', 'fs']]
    paths = [route, source, signoff, current, current_receipt, *screens, Path(__file__).resolve(), Path(sys.executable).resolve(), Path(pya.__file__).resolve(), Path(klayout.dbcore.__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    try:
        so = json.loads(signoff.read_text())
        for p in [route, source]:
            if so['sha256'].get(str(p)) != sha(p):
                raise ValueError('historical GDS/database signoff identities differ')
        cr = json.loads(current_receipt.read_text())
        if cr['artifacts'].get(str(current)) != sha(current):
            raise ValueError('current filled GDS identity differs')
        timing = []
        for p in screens:
            value = json.loads(p.read_text())
            if value['input_sha256'].get(str(route)) != sha(route):
                raise ValueError('historical timing used another digital database')
            timing.append(dict(receipt=str(p), corner=value['native_model_corner'], reported_slack_ns=value['corner_worst_slack_ns'], physical_timing_qualified=value['physical_timing_qualified']))
        save(output / 'inputs.json', dict(input_sha256=pins, scope='macro geometry identity and historical timing provenance only', CPU=29, memory_GiB=2, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_geometry_audit_resources', release_ready=False))
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            left, right = pya.Layout(), pya.Layout()
            left.read(str(source))
            right.read(str(current))
            result = compare_cells(left, right, 'IntegerPLL_ProgrammedCore')
            verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, **result, historical_internal_digital_timing=timing, historical_database_is_internal_digital_not_current_parent=True, current_parent_loading_and_clocks_qualified=False, native_cell_timing_models_qualified=False, historical_slacks_remeasured=False, parent_timing_qualified=False, physical_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='digital_macro_identity_audit_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
