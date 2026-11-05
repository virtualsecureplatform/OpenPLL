"""Test stock antenna rules with a wrapped cell and a connected large metal pad."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from common_v3 import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from extract_prototype_analog_capacitance_v2 import PDK, MAGIC

CELL = 'sky130_fd_sc_hs__buf_1'
TOP = 'AntennaGeometryControl'


def run(output):
    import pya
    directory = ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs'
    gds = directory/'gds/sky130_fd_sc_hs.gds'
    lef = directory/'lef/sky130_fd_sc_hs.lef'
    tech = PDK/'libs.tech/magic/sky130A.tech'
    source = pya.Layout(); source.read(str(gds))
    original = source.cell(CELL)
    if original is None:
        raise ValueError('source control cell absent')
    block = re.search(r'^MACRO '+CELL+r'\s*\n(.*?)^END '+CELL+r'\s*$', lef.read_text(), re.M|re.S)
    pin = re.search(r'^\s*PIN A\s*\n(.*?)^\s*END A\s*$', block[1], re.M|re.S) if block else None
    rectangle = re.search(r'LAYER li1\s*;\s*RECT\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*;', pin[1]) if pin else None
    if rectangle is None:
        raise ValueError('explicit li1 input pin required')
    coords = [round(float(v)/source.dbu) for v in rectangle.groups()]
    area = pya.Region(pya.Box(*coords))
    original_m1 = pya.Region(original.begin_shapes_rec(source.layer(67,20))).merged()
    if not (area-original_m1).is_empty():
        raise ValueError('LEF input rectangle is not covered by actual source metal')
    x, y = pya.Box(*coords).center().x, pya.Box(*coords).center().y
    output.mkdir(parents=True, exist_ok=False)
    inputs = [gds, lef, tech, Path(MAGIC), Path(__file__).resolve(),
              ROOT/'build/apptainer/openpll-release-modern.sif']
    pins = {str(p): sha(p) for p in inputs}
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    devices = []; results = []
    for name, pad in [('baseline', False), ('large_connected_metal3_pad', True)]:
        folder = output/name; folder.mkdir()
        layout = pya.Layout(); layout.dbu = source.dbu
        leaf = layout.create_cell(CELL); leaf.copy_tree(original)
        top = layout.create_cell(TOP); top.insert(pya.CellInstArray(leaf.cell_index(), pya.Trans()))
        def box(layer, x0, y0, x1, y1):
            top.shapes(layout.layer(*layer)).insert(pya.Box(round(x0/source.dbu), round(y0/source.dbu),
                                                         round(x1/source.dbu), round(y1/source.dbu)))
        if pad:
            cx, cy = x*source.dbu, y*source.dbu
            # A short two-via stack reaches a layer absent from the source cell.
            # The large pad lies outside the cell; no active/poly geometry changes.
            if not pya.Region(original.begin_shapes_rec(source.layer(70,20))).is_empty():
                raise ValueError('source control cell already uses metal3')
            box((67,44), cx-.085, cy-.085, cx+.085, cy+.085)
            box((68,20), cx-.15, cy-.15, cx+.15, cy+.15)
            box((68,44), cx-.075, cy-.075, cx+.075, cy+.075)
            box((69,20), cx-.2, cy-.2, cx+.2, cy+.2)
            box((69,44), cx-.1, cy-.1, cx+.1, cy+.1)
            box((70,20), cx-.2, cy-.2, 20.2, cy+.2)
            box((70,20), 20, cy-50, 1020, cy+50)
        fixture = folder/'fixture.gds'; layout.write(str(fixture))
        rc = folder/'minimal.magicrc'; rc.write_text('tech load {'+str(tech)+'}\n')
        script = folder/'control.tcl'
        script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{fixture}}}
load {TOP} -dereference
select top cell
flatten AntennaGeometryFlat
load AntennaGeometryFlat
cd {{{folder}}}
extract style ngspice()
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck
puts "ANTENNA_GEOMETRY_CONTROL_FEEDBACK=[feedback count]"
feedback save {{{folder}/antenna.feedback}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        with lease(1, 4, deadline):
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', rc, script], folder/'magic.log', deadline, 4)
        log = (folder/'magic.log').read_text()
        matches = re.findall(r'^ANTENNA_GEOMETRY_CONTROL_FEEDBACK=(\d+)\s*$', log, re.M)
        ext = folder/'AntennaGeometryFlat.ext'
        if len(matches) != 1 or not ext.exists():
            raise ValueError('native geometry control incomplete')
        rows = sorted(line for line in ext.read_text().splitlines() if line.startswith('device '))
        if not rows:
            raise ValueError('control transistor extraction absent')
        devices.append(rows)
        results.append(dict(case=name, feedback_entries=int(matches[0]), extracted_devices=len(rows)))
    detail = output/'results.json'; save(detail, results)
    verify(pins)
    if devices[0] != devices[1] or results[0]['feedback_entries'] != 0 or results[1]['feedback_entries'] <= 0:
        raise ValueError('stock-rule geometry control did not match')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): sha(p) for p in output.rglob('*') if p.is_file()},
         wrapped_stock_cell_baseline_has_no_antenna_feedback=True,
         large_connected_metal_pad_detected_under_unchanged_PDK_rules=True,
         transistor_geometry_and_connectivity_unchanged_between_controls=True,
         parent_or_final_candidate_antenna_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
