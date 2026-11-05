#!/usr/bin/env python3
"""Export and audit an assembly LEF from the current routed digital database.

Preserves pin geometry and blocks occupied routing layers. This is an assembly
input, not an intermacro route or physical signoff of the assembled PLL.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess

from check_compact_clock_tree import verify
from check_compact_mapping import LEF, TECH, OPENROAD
from run_dco_qualification import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    route = ROOT/'build/timing400/release_001/compact_incremental_headroom_001'
    verify(route/'assessment.json')
    physical = route/'signoff/assessment.json'
    signoff = json.loads(physical.read_text())
    assert signoff['diagnostic_physical_pass']
    for path, digest in signoff['sha256'].items():
        assert sha(path) == digest, path
    inputs = {str(p):sha(p) for p in [Path(__file__).resolve(), Path(OPENROAD),
        LEF, TECH, route/'route.odb', route/'assessment.json', physical, route/'signoff/route.gds']}
    out.mkdir(parents=True)
    abstract = out/'IntegerPLL_AcquiringCore.lef'
    script = f'''read_lef {TECH}
read_lef {LEF}
read_db {route}/route.odb
set block [ord::get_db_block]
set f [open {out}/source_pins.tsv w]
puts $f [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]
foreach term [$block getBTerms] {{
    puts $f [join [list PIN [$term getName] [$term getIoType] [$term getSigType]] "\\t"]
    foreach pin [$term getBPins] {{
        foreach box [$pin getBoxes] {{
            puts $f [join [list RECT [$term getName] [[$box getTechLayer] getName] [$box xMin] [$box yMin] [$box xMax] [$box yMax]] "\\t"]
        }}
    }}
}}
close $f
write_abstract_lef -bloat_occupied_layers {abstract}
'''
    (out/'export.tcl').write_text(script)
    with (out/'export.log').open('w') as log:
        subprocess.run([OPENROAD, '-no_init', '-exit', str(out/'export.tcl')],
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    source, geometry = {}, defaultdict(list)
    rows = [line.split('\t') for line in (out/'source_pins.tsv').read_text().splitlines()]
    assert rows[0][0] == 'UNITS'
    units = Decimal(rows[0][1])
    for fields in rows[1:]:
        if fields[0] == 'PIN':
            assert fields[1] not in source
            source[fields[1]] = tuple(fields[2:])
        else:
            assert fields[0] == 'RECT'
            geometry[fields[1]].append((fields[2], *map(int,fields[3:])))
    text = abstract.read_text()
    exported = {}
    for match in re.finditer(r'^\s*PIN\s+(\S+)\s*$', text, re.M):
        name = match[1]
        body = text[match.end():].split('END '+name,1)[0]
        direction, = re.findall(r'DIRECTION\s+(\w+)\s*;', body)
        use, = re.findall(r'USE\s+(\w+)\s*;', body)
        shapes = []
        layer = None
        for line in body.splitlines():
            fields = line.split()
            if fields and fields[0] == 'LAYER':
                layer = fields[1]
            if fields and fields[0] == 'RECT':
                assert layer
                coords = [Decimal(n)*units for n in fields[1:5]]
                assert all(v == v.to_integral_value() for v in coords)
                shapes.append((layer, *map(int, coords)))
        assert name not in exported
        exported[name] = (direction, use)
        assert sorted(shapes) == sorted(geometry[name]), name
    assert exported == source and all(geometry.values())
    assert source['VDD'] == ('INOUT', 'POWER') and source['VSS'] == ('INOUT', 'GROUND')
    assert len(source) == 357 and 'OBS' in text
    for path, digest in inputs.items():
        assert sha(path) == digest, path
    save(out/'assessment.json', dict(input_sha256=inputs,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        scalar_pins=357, exact_pin_rectangles_preserved=sum(map(len,geometry.values())),
        pin_directions_and_uses_preserved=True, occupied_routing_layers_blocked=True,
        physical_power_ports={'VDD':'VPWR and VPB', 'VSS':'VGND and VNB'},
        intermacro_routing_completed=False, assembled_lvs_passed=False,
        release_qualified=False, adopted=False, scope=__doc__))
    print('Exported digital macro LEF:357pins and exact routed pin rectangles audited.')


if __name__ == '__main__':
    main()
