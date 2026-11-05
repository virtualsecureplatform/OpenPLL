"""Cover actual GDS routing/cut geometry missing from a checked macro abstract."""
import argparse
import json
import re
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from audit_prototype_macro_interface_reuse import interface


def rectangles(text):
    pins, obs = {}, {}
    pin = None
    obstruction = False
    layer = None
    for line in text.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == 'PIN':
            pin = f[1]
        elif pin and f == ['END', pin]:
            pin = None
        elif f == ['OBS']:
            obstruction = True
        elif obstruction and f == ['END']:
            obstruction = False
        elif f[0] == 'LAYER' and (pin or obstruction):
            layer = f[1]
        elif f[0] == 'RECT' and (pin or obstruction):
            values = [float(x)*1000 for x in f[1:5]]
            if len(values) != 4 or any(abs(x-round(x)) > 1e-6 for x in values):
                raise ValueError('exact nanometer rectangle grid required')
            target = pins if pin else obs
            target.setdefault(layer, []).append(tuple(round(x) for x in values))
        elif f[0] in ('POLYGON', 'VIA') and (pin or obstruction):
            raise ValueError('unreviewed nonrectangular abstract geometry')
    return pins, obs


def add_obstructions(text, additions):
    pattern = re.compile(r'(^  OBS\n)(.*?)(^  END\s*$)', re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError('unique abstract obstruction block required')
    match = matches[0]
    extra = ''
    for layer, boxes in sorted(additions.items()):
        if not re.fullmatch(r'(li1|met[1-5]|mcon|via[234]?)', layer):
            raise ValueError('reviewed routing or cut layer required')
        if not boxes:
            continue
        extra += f'    LAYER {layer} ;\n'
        for box in boxes:
            if len(box) != 4 or not box[0] < box[2] or not box[1] < box[3]:
                raise ValueError('nonempty obstruction rectangle required')
            extra += '      RECT '+' '.join(f'{x/1000:.3f}' for x in box)+' ;\n'
    result = text[:match.end(2)]+extra+text[match.end(2):]
    if interface(result) != interface(text):
        raise ValueError('abstract interface changed')
    return result


def run(route, output):
    from klayout import db as pya
    receipt = route/'assessment.json'; signoff = route/'signoff/assessment.json'
    r, s = [json.loads(p.read_text()) for p in (receipt, signoff)]
    verify(r['input_sha256']); verify(r['artifacts']); verify(s['sha256'])
    if not r.get('digital_routing_completed') or not s.get('diagnostic_physical_pass'):
        raise ValueError('independently checked digital physical source required')
    lef = route/'digital.lef'; gds = route/'signoff/route.gds'
    text = lef.read_text(); metadata = interface(text); pin_boxes, old_boxes = rectangles(text)
    layout = pya.Layout(); layout.read(str(gds))
    if layout.dbu != .001 or layout.cell(metadata['master']) is None:
        raise ValueError('exact GDS master and nanometer database required')
    cell = layout.cell(metadata['master'])
    mapping = ROOT/'build/timing450/pdk/sky130A/libs.tech/klayout/tech/sky130A.map'
    layers = {}
    for line in mapping.read_text().splitlines():
        f = line.split()
        if len(f) == 4 and re.fullmatch(r'(li1|met[1-5]|mcon|via[234]?)', f[0]) and 'VIA' in f[1].split(','):
            pair = tuple(map(int, f[2:]))
            if f[0] in layers and layers[f[0]] != pair:
                raise ValueError('ambiguous physical layer map')
            layers[f[0]] = pair
    if set(layers) != {'li1','met1','met2','met3','met4','met5','mcon','via','via2','via3','via4'}:
        raise ValueError('complete routing/cut layer map required')
    additions = {}; controls = []

    def region(boxes):
        result = pya.Region()
        for box in boxes:
            result.insert(pya.Box(*box))
        return result

    for layer, pair in sorted(layers.items()):
        index = layout.find_layer(*pair)
        actual = pya.Region(cell.begin_shapes_rec(index)) if index is not None else pya.Region()
        pins = region(pin_boxes.get(layer, [])); existing = region(old_boxes.get(layer, []))
        missing = (actual-existing-pins).merged()
        shapes = list(missing.decompose_trapezoids_to_region().each())
        # Trapezoids on this rectilinear source must be rectangles; do not
        # silently replace nonrectangular shapes by their bounding boxes.
        if any(p.num_points() != 4 or p.area() != p.bbox().area() for p in shapes):
            raise ValueError('nonrectangular GDS routing geometry requires explicit support')
        boxes = [p.bbox() for p in shapes]
        additions[layer] = [(b.left,b.bottom,b.right,b.top) for b in boxes]
        if not (actual-existing-region(additions[layer])-pins).is_empty():
            raise ValueError('actual routing geometry remains uncovered')
        controls.append(dict(layer=layer,added_rectangles=len(additions[layer]),
                             added_area_um2=missing.area()*1e-6,all_actual_geometry_covered_except_ports=True))
    result = add_obstructions(text, additions)
    new_pins, new_obs = rectangles(result)
    if new_pins != pin_boxes:
        raise ValueError('pin geometry changed')
    for layer in layers:
        if not (region(old_boxes.get(layer, []))-region(new_obs.get(layer, []))).is_empty():
            raise ValueError('original obstruction geometry removed')
    output.mkdir(parents=True, exist_ok=False)
    target = output/'digital.lef'; target.write_text(result)
    detail = output/'coverage.json'; save(detail, controls)
    pins = {str(p): sha(p) for p in (receipt,signoff,lef,gds,mapping,Path(__file__).resolve(),
            Path(__file__).with_name('audit_prototype_macro_interface_reuse.py'))}
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in (target,detail)},
         candidate_source_sha256=r['candidate_source_sha256'],
         original_macro_geometry_and_pin_shapes_preserved=True,
         original_obstruction_geometry_preserved=True,
         all_actual_routing_and_cut_geometry_covered_except_ports=True,
         annotation_only_child_GDS_unchanged=True, interface_antenna_metadata_complete=False,
         new_parent_DRC_LVS_required=True, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route','output'):
        p.add_argument('--'+name, type=Path, required=True)
    a=p.parse_args();run(a.route.resolve(),a.output.resolve())
