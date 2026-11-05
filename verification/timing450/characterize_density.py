#!/usr/bin/env python3
"""Characterize standalone-core density windows without claiming chip signoff."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def origins(low, high, width, step):
    if width <= 0 or step <= 0 or high <= low:
        raise RuntimeError('Invalid density grid dimensions')
    # Full windows only. Do not invent material outside the known core.
    return list(range(low, high - width + 1, step))


def main():
    import pya
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Require a fresh output directory')
    gds = args.candidate / 'signoff/route.gds'
    previous = args.candidate / 'signoff/klayout_checks/global-density_assessment.json'
    receipt = json.loads(previous.read_text())
    expected = [(path, digest) for path, digest in receipt['sha256'].items() if path.endswith('/signoff/route.gds')]
    if len(expected) != 1 or sha(gds) != expected[0][1]:
        raise RuntimeError('Missing or stale GDS qualification evidence')
    inputs = {str(p): sha(p) for p in (gds, previous, Path(__file__).resolve())}
    layout = pya.Layout()
    layout.read(str(gds))
    cell = layout.cell('IntegerPLL_AcquiringCore')
    if cell is None or cell.bbox().empty() or layout.dbu <= 0:
        raise RuntimeError('Missing or empty core geometry')
    bbox = cell.bbox()
    # Match the existing installed density deck's drawing/fill selections.
    fills = (56, 36, 41, 34, 51, 59)
    regions = {}
    for layer, name, fill in zip(range(67, 73), ('li1', 'm1', 'm2', 'm3', 'm4', 'm5'), fills):
        region = pya.Region()
        for index in layout.layer_indices():
            info = layout.get_info(index)
            if (info.layer == layer and info.datatype not in (5, 10, 44)) or (info.layer == fill and info.datatype == 28):
                region += pya.Region(cell.begin_shapes_rec(index))
        region.merge()
        regions[name] = region
    tables = {}
    for size_um, step_um in ((50, 25), (700, 70)):
        size, step = round(size_um / layout.dbu), round(step_um / layout.dbu)
        xs = origins(bbox.left, bbox.right, size, step)
        ys = origins(bbox.bottom, bbox.top, size, step)
        windows = []
        for x in xs:
            for y in ys:
                box = pya.Box(x, y, x + size, y + size)
                clip = pya.Region(box)
                ratios = {name: (region & clip).area() / box.area() for name, region in regions.items()}
                if not all(0 <= ratio <= 1 for ratio in ratios.values()):
                    raise RuntimeError('Invalid clipped density')
                windows.append({'lower_left_um': [x * layout.dbu, y * layout.dbu], 'metal_area_fraction': ratios})
        tables[str(size_um)] = {'size_um': size_um, 'step_um': step_um, 'full_windows': len(windows),
                               'windows': windows, 'maximum_metal_area_fraction':
                               {name: max(w['metal_area_fraction'][name] for w in windows) for name in regions} if windows else None}
    for path, digest in inputs.items():
        if sha(path) != digest:
            raise RuntimeError('Inputs changed during density characterization')
    result = {'top': cell.name, 'dbu_um': layout.dbu,
              'bbox_um': [v * layout.dbu for v in (bbox.left, bbox.bottom, bbox.right, bbox.top)],
              'window_measurements': tables, 'sha256': inputs,
              'rule_source': 'https://skywater-pdk.readthedocs.io/en/main/rules/periphery.html',
              'full_windowed_density_signoff_pass': False, 'release_qualified': False, 'selected': False,
              'limitations': ['Standalone-core bounding box is the diagnostic domain, not an assembled die boundary',
                              'Large windows extending outside the core require assembled chip geometry',
                              'Raw drawing/fill unions; process applicability, derived oxide masks, waffle/exclusion handling and die-edge policy remain unqualified']}
    args.output.mkdir(parents=True)
    (args.output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('window_measurements', 'sha256')}))
    print(json.dumps({k: {'full_windows': v['full_windows'], 'maxima': v['maximum_metal_area_fraction']} for k, v in tables.items()}))


if __name__ == '__main__':
    main()
