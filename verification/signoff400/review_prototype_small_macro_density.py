"""Review raw stock-PDK density tiles when its 700um applicability guard stops reporting.

This retains the stock clipped-edge weighting and thresholds. It never converts
the failed stock wrapper into a pass or qualifies chip integration density.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re

from common_v3 import save, sha, verify

LAYERS = ('FOM', 'POLY', 'LI1', 'MET1', 'MET2', 'MET3', 'MET4', 'MET5')
LIMITS = dict(FOM=('0.33', '0.57'), LI1=('0.35', '0.60'),
              MET1=('0.35', '0.60'), MET2=('0.35', '0.60'),
              MET3=('0.35', '0.60'), MET4=('0.35', '0.60'), MET5=('0.45', '0.76'))


def measure(text, die):
    if ('Magic exited with status 0' not in text or '\nEnded: ' not in text
            or 'cannot run density checks.' not in text
            or any(s in text for s in ('Input off lambda grid', 'snapped to grid', 'Traceback'))):
        raise ValueError('complete native tiles and explicit stock applicability stop required')
    fields = {}
    for name in ('XTILES', 'YTILES', 'XFRAC', 'YFRAC'):
        matches = re.findall(r'^'+name+r': (\S+)$', text, re.M)
        if len(matches) != 1:
            raise ValueError('ambiguous tile geometry')
        fields[name] = Decimal(matches[0])
    nx, ny = int(fields['XTILES']), int(fields['YTILES'])
    xf, yf = fields['XFRAC'], fields['YFRAC']
    if not (nx > 0 and ny > 0 and (nx < 10 or ny < 10) and 0 < xf <= 1 and 0 < yf <= 1):
        raise ValueError('small macro applicability required')
    # Raw Tcl fractions are printed with double precision.
    widths = (Decimal(die[2]-die[0]), Decimal(die[3]-die[1]))
    if any(abs(actual-expected) > Decimal('0.000001') for actual, expected in
           zip(((nx-1+xf)*70000, (ny-1+yf)*70000), widths)):
        raise ValueError('raw tile bounds differ from declared macro')
    tiles = {}
    for x, y, body in re.findall(r'Density results for tile x=(\d+) y=(\d+)\n(.*?)(?=Density results for tile|Ended:)', text, re.S):
        key = (int(x), int(y))
        pairs = re.findall(r'^(FOM|POLY|LI1|MET[1-5]): (\S+)$', body, re.M)
        if key in tiles or len(pairs) != len(LAYERS) or set(dict(pairs)) != set(LAYERS):
            raise ValueError('duplicate or incomplete tile')
        tiles[key] = {k: Decimal(v) for k, v in pairs}
        if not all(v.is_finite() and 0 <= v <= 1 for v in tiles[key].values()):
            raise ValueError('invalid tile density')
    if set(tiles) != {(x, y) for x in range(nx) for y in range(ny)}:
        raise ValueError('missing or unexpected tiles')
    area = (nx-1+xf)*(ny-1+yf)
    results = {}
    for layer in LAYERS:
        value = sum(row[layer]*(xf if x == nx-1 else 1)*(yf if y == ny-1 else 1)
                    for (x, y), row in tiles.items())/area
        limits = LIMITS.get(layer)
        results[layer] = dict(global_density=str(value), limits=limits,
            within_limits=None if limits is None else Decimal(limits[0]) <= value <= Decimal(limits[1]))
    return dict(raw_tiles=len(tiles), results=results,
                constrained_global_checks=len(LIMITS),
                failed_global_checks=sum(r['within_limits'] is False for r in results.values()))


def run(source, output):
    manifest = source/'input_manifest.json'
    record = json.loads(manifest.read_text())
    verify(record['input_sha256'])
    method = Path(next(p for p in record['input_sha256'] if p.endswith('/check_density.py')))
    code = method.read_text()
    for low, high in LIMITS.values():
        if '< '+low not in code or '> '+high not in code:
            raise ValueError('stock thresholds changed')
    log = source/'density.log'
    text = log.read_text()
    result = measure(text, record['declared_die_nm'])
    warnings = re.findall(r'^.*(?:Error while reading|Warning:|Error limit set).*$' , text, re.M)
    pins = {str(p): sha(p) for p in (manifest, log, method, Path(__file__).resolve(), Path(__file__).with_name('common_v3.py'))}
    output.mkdir(parents=True, exist_ok=False)
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={}, **result,
        stock_wrapper_passed=False, native_tile_measurement_completed=True,
        source_geometry_warnings=warnings,
        global_density_limits_met=result['failed_global_checks'] == 0,
        nominal_window_um=700, step_um=70, stepped_windows_available=False,
        chip_integration_density_qualified=False, density_qualified=False,
        physical_integrity_qualified=False, release_ready=False))
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('density', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.density.resolve(), args.output.resolve())
