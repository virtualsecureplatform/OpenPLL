#!/usr/bin/env python3
"""Audit macro placement/connectivity before top routing; never physical signoff."""
import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT, sha, save


def check(connections):
    assert {k:len(v) for k,v in connections.items()} == {'digital':357, 'oscillator':308, 'detector':9}
    for pin, net in connections['digital'].items():
        assert net == {'VDD':'VPWR', 'VSS':'VGND'}.get(pin,pin), (pin,net)
    for pin, net in connections['oscillator'].items():
        assert net == pin, (pin,net)
    for pin, net in connections['detector'].items():
        assert net == {'REF':'REFCLK','CLKDIVR':'CLKDIV_RETIMED','RESET_N':'BBPD_RESET_N'}.get(pin,pin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--floorplan', required=True, type=Path)
    args = parser.parse_args()
    out = args.floorplan.resolve()
    assert not (out/'assessment.json').exists()
    definition = (out/'floorplan.def').read_text()
    units = int(re.search(r'UNITS DISTANCE MICRONS (\d+) ;', definition)[1])
    die = tuple(map(int, re.search(r'DIEAREA \( (\d+) (\d+) \) \( (\d+) (\d+) \)', definition).groups()))
    assert die[0:2] == (0,0)
    base = ROOT/'build/timing400/release_001'
    top, abstract = base/'candidate_top_004', base/'digital_macro_abstract_001'
    verify(top/'assessment.json'); verify(abstract/'assessment.json')
    original = (top/'candidate_top.v').read_text()
    assert (out/'physical_top.v').read_text() == original.replace(
        'IntegerPLL_AcquiringCore digital (',
        'IntegerPLL_AcquiringCore digital (.VDD(VPWR), .VSS(VGND), ')
    connections, placements = defaultdict(dict), {}
    for line in (out/'connections.tsv').read_text().splitlines():
        f = line.split('\t')
        if f[0] == 'PIN':
            assert f[2] not in connections[f[1]]
            connections[f[1]][f[2]] = f[3]
        else:
            assert f[0] == 'INST' and f[1] not in placements
            placements[f[1]] = dict(master=f[2], bbox_dbu=list(map(int,f[3:])))
    check(connections)
    assert placements['digital']['master'] == 'IntegerPLL_AcquiringCore'
    assert placements['detector']['master'] == 'IntegerPLL_BBPD'
    assert placements['oscillator']['master'].endswith('C1FINE160')
    for p in placements.values():
        x0,y0,x1,y1 = p['bbox_dbu']
        assert die[0] <= x0 < x1 <= die[2] and die[1] <= y0 < y1 <= die[3]
    for a,b in combinations(placements.values(),2):
        ax0,ay0,ax1,ay1 = a['bbox_dbu'];bx0,by0,bx1,by1 = b['bbox_dbu']
        assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0
    faults = []
    for label,instance,pin,value in [('detector_reset','detector','RESET_N','RESET_N'),
                                    ('fine_bit_order','oscillator','DCO_THERM[0]','DCO_THERM[254]'),
                                    ('digital_power','digital','VDD','VGND')]:
        bad = {k:dict(v) for k,v in connections.items()};bad[instance][pin] = value
        try:
            check(bad)
        except AssertionError:
            faults.append(label)
        else:
            raise AssertionError('fault accepted: '+label)
    script = (out/'floorplan.tcl').read_text()
    paths = [Path(p) for p in re.findall(r'^read_lef (.+)$',script,re.M)]
    paths += [Path(__file__).resolve(),Path(OPENROAD),top/'assessment.json',abstract/'assessment.json']
    save(out/'assessment.json', dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        placements=placements, die_size_um=[die[2]/units,die[3]/units], macro_instances=3,
        connected_macro_pins=674, exact_signal_and_power_connections_passed=True,
        no_macro_overlap=True, all_macros_inside_die=True, rejected_faults=faults,
        top_pin_placement_completed=False, intermacro_routing_completed=False,
        power_grid_completed=False, assembled_lvs_passed=False,
        physical_timing_qualified=False, release_qualified=False, adopted=False, scope=__doc__))
    print('Audited three placed macros,674 signal/power connections and three negative controls.')


if __name__ == '__main__':
    main()
