"""Audit the actual routed enable chain and record nominal interstage timing.

This records connectivity, placement and a supplied-TT path. It does not set a
metastability reliability target or qualify reset timing and asynchronous CDC.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge_v2 import execute
from synthesize_async_enable_candidate import capture_chain
sys.path.insert(0, str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD, LIB


def topology(module, chain):
    cells = module['cells']
    drivers, loads = defaultdict(list), defaultdict(list)
    for name, cell in cells.items():
        for pin, bits in cell['connections'].items():
            for bit in bits:
                if cell['port_directions'][pin] == 'output':
                    drivers[bit].append((name, pin))
                elif cell['port_directions'][pin] == 'input':
                    loads[bit].append((name, pin))
    def buffer(name):
        cell = cells[name]
        match = re.fullmatch(r'sky130_fd_sc_hs__(buf|clkbuf|inv|clkinv)_\d+', cell['type'])
        if not match:
            return None
        inputs = [p for p,d in cell['port_directions'].items() if d == 'input']
        outputs = [p for p,d in cell['port_directions'].items() if d == 'output']
        if inputs != ['A'] or len(outputs) != 1:
            raise ValueError('unsupported transparent buffer ports')
        return cell['connections']['A'][0], cell['connections'][outputs[0]][0], match[1] in ('inv','clkinv')
    def path(source, destination):
        bit, inverted, seen, records = destination, False, set(), []
        while bit != source:
            if bit in seen or len(drivers[bit]) != 1:
                raise ValueError('unique acyclic capture signal driver required')
            seen.add(bit)
            name, pin = drivers[bit][0]
            info = buffer(name)
            if info is None or info[1] != bit:
                raise ValueError('capture path contains non-buffer logic')
            bit, _, polarity = info
            inverted ^= polarity
            records.append(dict(instance=name, master=cells[name]['type']))
        if inverted:
            raise ValueError('capture signal polarity changed')
        return list(reversed(records))
    actual = []
    for stage in chain:
        names = [n for n in (stage['instance'], '\\'+stage['instance']) if n in cells]
        if len(names) != 1:
            raise ValueError('exact unique routed capture cell identity required')
        name = names[0]
        cell = cells[name]
        if not cell['type'].startswith('sky130_fd_sc_hs__dfrtp_'):
            raise ValueError('positive-edge asynchronous-clear capture cell required')
        actual.append(dict(instance=name, master=cell['type'], connections=cell['connections']))
    ref = module['ports']['REFCLK']['bits'][0]
    raw = module['ports']['PLL_ENABLE']['bits'][0]
    reset = module['netnames']['ref_reset_pipe']['bits'][1]
    paths = dict(raw_to_stage0=path(raw, actual[0]['connections']['D'][0]),
        stage0_to_stage1=path(actual[0]['connections']['Q'][0], actual[1]['connections']['D'][0]),
        clocks=[path(ref, c['connections']['CLK'][0]) for c in actual],
        resets=[path(reset, c['connections']['RESET_B'][0]) for c in actual])
    pending = [actual[0]['connections']['Q'][0]]
    seen, sinks, passive = set(), [], []
    while pending:
        bit = pending.pop()
        if bit in seen:
            raise ValueError('reconvergent or cyclic first-stage fanout requires review')
        seen.add(bit)
        for name, pin in loads[bit]:
            info = buffer(name)
            if info is not None:
                pending.append(info[1])
            elif cells[name]['type'] == 'sky130_fd_sc_hs__diode_2' and pin == 'DIODE':
                passive.append(name)
            else:
                sinks.append((name, pin))
    if sinks != [(actual[1]['instance'], 'D')]:
        raise ValueError('first-stage capture must feed only the second-stage data pin')
    if any(bit in seen for port in module['ports'].values() if port['direction'] == 'output' for bit in port['bits']):
        raise ValueError('first capture stage exposed at a macro output')
    return dict(cells=actual, paths=paths, first_stage_functional_sinks=sinks,
                first_stage_passive_diode_loads=passive)


def run(route, mapping, proof, placement, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {27})
    paths = [route/'assessment.json', mapping/'assessment.json', proof/'assessment.json',
             placement/'assessment.json', mapping/'mapped.json', proof/'before_projection.json',
             route/'route.odb', route/'route.nom.spef', placement/'diagnostic.sdc', LIB, Path(OPENROAD),
             Path(__file__).resolve(), *(Path(__file__).with_name(n) for n in
             ('common_v3.py','resources.py','compiled_charge_v2.py','synthesize_async_enable_candidate.py'))]
    receipts = [json.loads(p.read_text()) for p in paths[:4]]
    for receipt in receipts:
        verify(receipt['input_sha256'])
        verify(receipt['artifacts'])
    routed, mapped, proven, placed = receipts
    if not (proven['all_transition_and_output_functions_equivalent']
            and proven['corrupted_reset_function_rejected']):
        raise ValueError('actual routed equivalence and rejecting control required')
    if proven['input_sha256'].get(str(route/'assessment.json')) != sha(route/'assessment.json') or proven['input_sha256'].get(str(mapping/'mapped.json')) != sha(mapping/'mapped.json'):
        raise ValueError('proof must bind exact route and mapping')
    if routed['candidate_source_sha256'] != mapped['candidate_source_sha256'] or routed['candidate_source_sha256'] != placed['candidate_source_sha256']:
        raise ValueError('all physical steps must bind the same candidate sources')
    gold = json.loads((mapping/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
    module = json.loads((proof/'before_projection.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
    result = topology(module, capture_chain(gold))
    names = [r['instance'].removeprefix('\\') for r in result['cells']]
    pins = {str(p): sha(p) for p in paths}
    script = output/'query.tcl'
    script.write_text(f'''read_liberty {{{LIB}}}
read_db {{{route/'route.odb'}}}
source {{{placement/'diagnostic.sdc'}}}
read_spef {{{route/'route.nom.spef'}}}
set_propagated_clock [all_clocks]
set block [ord::get_db_block]
set f [open {{{output/'capture_geometry.tsv'}}} w]
puts $f "units\t[$block getDbUnitsPerMicron]"
foreach name {{{' '.join(names)}}} {{
 set inst [$block findInst $name]
 if {{$inst eq "NULL"}} {{error "capture instance missing from actual database"}}
 puts $f [join [concat [list $name [[$inst getMaster] getName]] [$inst getLocation] [list [$inst getOrient]]] "\t"]
}}
close $f
report_checks -from [get_pins {{{names[0]}/Q}}] -to [get_pins {{{names[1]}/D}}] -path_delay max -format full_clock_expanded -digits 9 > {{{output/'interstage_max.rpt'}}}
report_checks -from [get_pins {{{names[0]}/Q}}] -to [get_pins {{{names[1]}/D}}] -path_delay min -format full_clock_expanded -digits 9 > {{{output/'interstage_min.rpt'}}}
''')
    pins[str(script)] = sha(script)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+300
    with lease(1, 2, deadline):
        execute([OPENROAD,'-no_init','-exit',script], output/'query.log', deadline, 2)
    rows = [line.split('\t') for line in (output/'capture_geometry.tsv').read_text().splitlines()]
    if len(rows) != 3 or rows[0][0] != 'units' or [r[0] for r in rows[1:]] != names:
        raise ValueError('complete exact capture geometry required')
    units = int(rows[0][1])
    positions = [list(map(int,r[2:4])) for r in rows[1:]]
    distance = sum(abs(a-b) for a,b in zip(*positions))/units
    for name in ('interstage_min.rpt','interstage_max.rpt'):
        text = (output/name).read_text()
        if not all(n in text for n in names) or 'slack' not in text or 'No paths found' in text:
            raise ValueError('explicit interstage timing path required')
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in output.iterdir() if p.is_file()},
        routed_topology=result, first_stage_fanout_only_second_stage_D=True,
        capture_origin_Manhattan_distance_um=distance, capture_positions_database_units=positions,
        nominal_interstage_min_max_paths_reported=True, timing_temperature_C=25,
        reset_CDC_qualified=False, metastability_reliability_qualified=False,
        actual_startup_frequency_range_qualified=False, selected_layout_promoted=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('route','mapping','proof','placement','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args,n).resolve() for n in ('route','mapping','proof','placement','output')))
