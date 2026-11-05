#!/usr/bin/env python3
"""Recompute the stock PDK density report from its raw tile measurements.

Retains the PDK's clipped edge-window convention. A density failure is
recorded explicitly, independent of the native process's zero exit code.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('density','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    source, out = args.density.resolve(), args.output.resolve()
    native = verify(source/'native_completion.json')
    assert native['exit_code'] == 0
    text = (source/'density.log').read_text()
    assert text.rstrip().endswith('Done!') and 'Magic exited with status 0' in text
    assert not any(s in text for s in ('Input off lambda grid','snapped to grid','Traceback'))
    nx = int(re.search(r'^XTILES: (\d+)$',text,re.M)[1])
    ny = int(re.search(r'^YTILES: (\d+)$',text,re.M)[1])
    xf = Decimal(re.search(r'^XFRAC: (\S+)$',text,re.M)[1])
    yf = Decimal(re.search(r'^YFRAC: (\S+)$',text,re.M)[1])
    layers = ('FOM','POLY','LI1','MET1','MET2','MET3','MET4','MET5')
    tiles = {}
    for x,y,body in re.findall(r'Density results for tile x=(\d+) y=(\d+)\n(.*?)(?=Density results for tile|Ended:)',text,re.S):
        key = (int(x),int(y))
        assert key not in tiles
        row = dict(re.findall(r'^(FOM|POLY|LI1|MET[1-5]): (\S+)$',body,re.M))
        assert set(row) == set(layers)
        tiles[key] = {k:Decimal(v) for k,v in row.items()}
        assert all(0 <= value <= 1 for value in tiles[key].values())
    assert set(tiles) == {(x,y) for x in range(nx) for y in range(ny)}

    def integrate(layer,x0,y0,x1,y1):
        area = value = Decimal(0)
        for x in range(x0,x1):
            for y in range(y0,y1):
                weight = (xf if x==nx-1 else Decimal(1))*(yf if y==ny-1 else Decimal(1))
                area += weight
                value += weight*tiles[x,y][layer]
        return value/area

    names = dict(FOM='FOM',POLY='POLY',LI1='LI',MET1='MET1',MET2='MET2',MET3='MET3',MET4='MET4',MET5='MET5')
    global_text = text.split('Whole-chip (global) density results:',1)[1]
    step_text = text.split('Stepped area density results',1)[1].split('Whole-chip (global)',1)[0]
    results = {}
    checks = failures = 0
    limits = {'FOM':('0.33','0.57'),'LI1':('0.35','0.60'),
        'MET1':('0.35','0.60'),'MET2':('0.35','0.60'),
        'MET3':('0.35','0.60'),'MET4':('0.35','0.60'),'MET5':('0.45','0.76')}
    # These exact thresholds must remain present in the pinned PDK method.
    method = Path(next(p for p in native['input_sha256'] if p.endswith('/check_density.py')))
    code = method.read_text()
    for low,high in limits.values():
        assert '< '+low in code and '> '+high in code
    for layer in layers:
        heading = names[layer]
        value = integrate(layer,0,0,nx,ny)
        printed = Decimal(re.search(r'^'+heading+r' Density: (\S+)$',global_text,re.M)[1])
        assert abs(value-printed) <= Decimal('0.000501'), layer
        section = step_text.split(heading+' Density:\n',1)[1].split('\n\n',1)[0]
        window_rows = re.findall(r'Tile \((\d+), (\d+)\):\s+(\S+)',section)
        assert len(window_rows) == (nx-9)*(ny-9)
        windows = []
        for x,y,rounded in window_rows:
            x,y = int(x),int(y)
            measured = integrate(layer,x,y,x+10,y+10)
            assert abs(measured-Decimal(rounded)) <= Decimal('0.000501'), (layer,x,y)
            windows.append(dict(x=x,y=y,density=str(measured)))
        failed = []
        if layer in limits:
            low,high = map(Decimal,limits[layer])
            checks += 1+len(windows)
            if not low <= value <= high:
                failed.append('global')
            failed += [f'window({r["x"]},{r["y"]})' for r in windows if not low <= Decimal(r['density']) <= high]
            failures += len(failed)
        results[layer] = dict(global_density=str(value),windows=windows,
            limits=list(limits[layer]) if layer in limits else None,failed_checks=failed)
    assert failures == len(re.findall(r'^\*\*\*Error:',text,re.M))
    out.mkdir(parents=True,exist_ok=False)
    files = [Path(__file__).resolve(),source/'native_completion.json',source/'density.log',method]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
        tiles=nx*ny,nominal_window_um=700,step_um=70,clipped_edge_windows_retained=True,
        independently_recomputed_global_and_window_values=True,
        constrained_density_checks=checks,failed_density_checks=failures,
        stock_density_checks_passed=failures==0,results=results,
        density_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print(json.dumps(dict(raw_tiles=nx*ny,checks=checks,failed=failures)))


if __name__ == '__main__':
    main()
