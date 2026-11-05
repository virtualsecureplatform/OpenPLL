#!/usr/bin/env python3
"""Audit the explicit power bridges; connectivity is not DRC or EM/IR signoff."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from audit_candidate_floorplan import check
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT, sha, save


def dump(directory, database, label):
    script = f'''read_db {database}
set f [open {directory}/{label}.tsv w]
set block [ord::get_db_block]
foreach inst [$block getInsts] {{
    foreach pin [$inst getITerms] {{
        puts $f [join [list PIN [$inst getName] [[$pin getMTerm] getName] [[$pin getNet] getName]] "\\t"]
    }}
}}
foreach net [$block getNets] {{
    foreach wire [$net getSWires] {{
        foreach box [$wire getWires] {{
            set layer VIA
            if {{![$box isVia]}} {{set layer [[$box getTechLayer] getName]}}
            puts $f [join [list BOX [$net getName] $layer [$box xMin] [$box yMin] [$box xMax] [$box yMax]] "\\t"]
        }}
    }}
}}
close $f
'''
    path = directory/f'{label}.tcl'
    path.write_text(script)
    with (directory/f'{label}.log').open('w') as stream:
        subprocess.run([OPENROAD,'-no_init','-exit',str(path)],stdout=stream,
                       stderr=subprocess.STDOUT,check=True,timeout=60)
    connections, boxes = {}, Counter()
    for line in (directory/f'{label}.tsv').read_text().splitlines():
        f = line.split('\t')
        if f[0] == 'PIN':
            connections.setdefault(f[1],{})[f[2]] = f[3]
        else:
            assert f[0] == 'BOX'
            boxes[(f[1],f[2],*map(int,f[3:]))] += 1
    check(connections)
    return connections, boxes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    out.mkdir(parents=True)
    base = ROOT/'build/timing400/release_001'
    before = base/'candidate_power_grid_006'
    after = base/'candidate_power_grid_013'
    con0, boxes0 = dump(out,before/'power_grid.odb','before')
    con1, boxes1 = dump(out,after/'power_grid.odb','after')
    assert con0 == con1 and not (boxes0-boxes1)
    expected, bridges = Counter(), []
    floorplan = json.loads((base/'candidate_floorplan_003/assessment.json').read_text())
    for line in (after/'bridges.tsv').read_text().splitlines():
        net,*coords = line.split('\t')
        x0,y0,x1,y1,gap = map(int,coords)
        assert net in ('VPWR','VGND') and y1-y0 == 1600
        assert 0 < gap <= 30000 and x1-x0 == gap+400
        assert all(n%5==0 for n in (x0,y0,x1,y1))
        for p in floorplan['placements'].values():
            a,b,c,d = p['bbox_dbu']
            assert x1 <= a-3000 or x0 >= c+3000 or y1 <= b-3000 or y0 >= d+3000
        other = 'VGND' if net == 'VPWR' else 'VPWR'
        for (supply,layer,a,b,c,d) in boxes1:
            if supply == other and layer == 'met5':
                assert x1 <= a-1600 or x0 >= c+1600 or y1 <= b-1600 or y0 >= d+1600
        expected[(net,'met5',x0,y0,x1,y1)] += 1
        bridges.append((net,x0,y0,x1,y1))
    assert boxes1-boxes0 == expected and sum(expected.values()) == 70
    log = (after/'power_grid.log').read_text()
    assert '[ERROR' not in log
    assert all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND'))
    # Reproduce the special router's ring-selection count from pinned source.
    ring_counts = {}
    for net in ('VPWR','VGND'):
        shapes = [key[2:] for key,count in boxes0.items() if key[0]==net for _ in range(count)]
        max_x = max(c-a for a,b,c,d in shapes)
        max_y = max(d-b for a,b,c,d in shapes)
        thickness_x = max(c-a for a,b,c,d in shapes if d-b==max_y)
        thickness_y = max(d-b for a,b,c,d in shapes if c-a==max_x)
        selected = [(a,b,c,d) for a,b,c,d in shapes if
                    (c-a==max_x and d-b==thickness_y) or (c-a==thickness_x and d-b==max_y)]
        ring_counts[net] = len(selected)
    files = [Path(__file__).resolve(),Path(__file__).with_name('audit_candidate_floorplan.py'),
             Path(OPENROAD),base/'candidate_floorplan_003/assessment.json',
             before/'power_grid.odb',before/'power_grid.tcl',after/'power_grid.odb',
             after/'power_grid.tcl',after/'power_grid.def',after/'power_grid.log',after/'bridges.tsv',
             base/'pdn_source_audit_001/sroute.cpp']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        existing_power_shapes_preserved=True,existing_vias_preserved=True,
        added_metal5_bridges=70,unique_added_bridges=len(expected),
        macro_connections_unchanged=674,bridge_macro_clearance_um=3,
        bridge_opposite_net_metal5_clearance_um=1.6,
        main_rail_connectivity_passed=True,body_bias_rails_still_separate=True,
        special_router_ring_selection_counts=ring_counts,special_router_supported_groups=4,
        full_power_grid_drc_passed=False,em_ir_qualified=False,
        physical_noise_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Audited70bridges, preserved prior shapes/vias and674bindings; both main rails connected.')


if __name__ == '__main__':
    main()
