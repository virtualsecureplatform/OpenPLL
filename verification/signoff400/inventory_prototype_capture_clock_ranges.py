"""Check every capture clock against its actual native constraint-table maximum.

A diagnostic model-domain check; this does not qualify timing or CDC.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import save, sha, verify
from compiled_charge_v2 import execute
from resources import lease
from screen_prototype_decision_hold_phase_v3 import OPENROAD


def table_maxima(text, masters):
    result = {}
    for master in masters:
        marker = 'cell ('+master+')'
        if text.count(marker) != 1:
            raise ValueError('one native library cell required: '+master)
        start = text.index(marker); end = text.find('\n  cell (', start+1)
        cell = text[start:end if end >= 0 else len(text)]
        tables = re.findall(r'(?:rise|fall)_constraint \(capture\)\s*\{\s*index_1 \([^;]*;\s*index_2 \("([^"]+)"\)', cell)
        if not tables:
            raise ValueError('native capture constraint tables required: '+master)
        maxima = []
        for row in tables:
            values = [float(x) for x in row.split(',')]
            if (not values or not all(math.isfinite(v) and v >= 0 for v in values)
                    or any(a >= b for a, b in zip(values, values[1:])) or values[-1] <= 0):
                raise ValueError('finite increasing clock constraint axis required')
            maxima.append(values[-1]*1e-9)
        result[master] = min(maxima)
    return result


def run(route, phase, inventory, views, output):
    records = [path/'assessment.json' for path in (route, phase, inventory, views)]
    rr, pr, ir, vr = records
    r, p, i, v = [json.loads(path.read_text()) for path in records]
    for record in (r, p, i, v):
        verify(record['input_sha256']); verify(record['artifacts'])
    if (p['input_sha256'].get(str(ir)) != sha(ir)
            or i['input_sha256'].get(str(rr)) != sha(rr)):
        raise ValueError('phase, inventory and route must bind the same candidate')
    corner = p['native_model_corner']
    if corner not in ('tt', 'ff', 'ss', 'sf', 'fs'):
        raise ValueError('supported native corner required')
    graph = inventory/'routed.json'
    cells = json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']['cells']
    ffs = {name.lstrip('\\'): cell['type'] for name, cell in cells.items()
           if cell['type'].startswith(('sky130_fd_sc_hs__dfrtp_', 'sky130_fd_sc_hs__dfstp_'))}
    if len(ffs) != 481 or i['sequential_cells'] != len(ffs):
        raise ValueError('complete frozen 481-cell capture inventory required')
    libraries = [views/f'{corner}_{edge}.lib' for edge in ('early', 'late')]
    bounds = [table_maxima(lib.read_text(), set(ffs.values())) for lib in libraries]
    limits = {master: min(b[master] for b in bounds) for master in set(ffs.values())}
    original = phase/'screen.tcl'
    prefix = original.read_text().split('report_parasitic_annotation', 1)[0]
    # The actual queried libraries and routed database must occur in the retained setup.
    if any(str(path) not in prefix for path in (*libraries, route/'route.odb')):
        raise ValueError('native setup does not use the pinned database and libraries')
    deadline = json.loads((route/'owner.json').read_text())['deadline_uptime']
    if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
        raise TimeoutError('original route deadline expired')
    output.mkdir(parents=True, exist_ok=False)
    table = output/'clock_slews.tsv'
    query = 'set f [open {'+str(table)+'} w]\nputs $f [join {cell rise_min_s rise_max_s fall_min_s fall_max_s} [format %c 9]]\n'
    for name in sorted(ffs):
        if any(c in name for c in '{}\n\r') or name.endswith('\\'):
            raise ValueError('safe native instance name required')
        query += ('set p [sta::get_port_pin_error pin {'+name+'/CLK}]\n'
                  'set vertices [$p vertices]\n'
                  'if {[llength $vertices]!=1} {error "one capture clock vertex required"}\n'
                  'set v [lindex $vertices 0]\nputs $f [join [list {'+name+'} '
                  '[$v slew rise min] [$v slew rise max] [$v slew fall min] [$v slew fall max]] [format %c 9]]\n')
    query += 'close $f\nputs "CAPTURE_CLOCK_QUERY_COMPLETE"\nexit\n'
    script = output/'query.tcl'; script.write_text(prefix+query)
    inputs = {str(path): sha(path) for path in (*records, graph, original, script,
        *libraries, route/'owner.json', Path(OPENROAD), Path(__file__).resolve())}
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with lease(1, 4, deadline):
        execute([OPENROAD, '-no_init', '-exit', script], output/'query.log', deadline, 4)
    if 'CAPTURE_CLOCK_QUERY_COMPLETE' not in (output/'query.log').read_text():
        raise ValueError('native clock query incomplete')
    with table.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if len(rows) != len(ffs) or {row['cell'] for row in rows} != set(ffs):
        raise ValueError('every capture cell must occur exactly once')
    violations = []; maximum = 0
    for row in rows:
        values = [float(row[key]) for key in ('rise_min_s', 'rise_max_s', 'fall_min_s', 'fall_max_s')]
        if not all(math.isfinite(x) and x >= 0 for x in values):
            raise ValueError('finite nonnegative native clock slews required')
        maximum = max(maximum, *values)
        limit = limits[ffs[row['cell']]]
        if max(values) > limit+1e-15:
            violations.append(dict(cell=row['cell'], master=ffs[row['cell']],
                maximum_clock_slew_ps=max(values)*1e12, characterized_maximum_ps=limit*1e12))
    verify(inputs); save(output/'violations.json', violations)
    save(output/'assessment.json', dict(input_sha256=inputs,
        artifacts={str(output/name): sha(output/name) for name in ('query.log', 'clock_slews.tsv', 'violations.json')},
        corner=corner, capture_cells=len(ffs), maximum_clock_slew_ps=maximum*1e12,
        characterized_clock_maximum_ps_by_master={k: x*1e12 for k, x in limits.items()},
        all_capture_clock_slews_inside_characterized_maximum=not violations,
        outside_model_clock_range=len(violations), original_route_deadline_preserved=True,
        digital_timing_qualified=False, physical_CDC_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'phase', 'inventory', 'views', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, name).resolve() for name in ('route', 'phase', 'inventory', 'views', 'output')))
