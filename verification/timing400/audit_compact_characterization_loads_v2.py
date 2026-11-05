#!/usr/bin/env python3
"""Compare routed wire-only capacitance observations with prepared cell loads.

SPEF PIN_CAP NONE totals exclude sink/diode capacitance and are not effective
loads or guaranteed lower bounds under coupling. No domain exclusion, timing
envelope, nonmonotone-waveform waiver or release qualification is made.
"""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import re

from check_compact_mapping import OPENROAD, TECH, LEF, run
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def wire_caps(path):
    mapping, caps = {}, {}
    text = path.read_text()
    assert '*C_UNIT 1 PF' in text and '"PIN_CAP NONE"' in text
    in_names = False
    for line in text.splitlines():
        if line == '*NAME_MAP':
            in_names = True
        elif line.startswith('*PORTS'):
            in_names = False
        elif in_names and re.match(r'^\*\d+\s', line):
            key, value = line.split(maxsplit=1)
            assert key not in mapping
            mapping[key] = re.sub(r'\\(.)', r'\1', value)
        elif line.startswith('*D_NET '):
            _, key, raw = line.split()
            name = mapping[key]
            cap = float(raw)
            assert name not in caps and math.isfinite(cap) and cap >= 0
            caps[name] = cap
    assert caps
    return caps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('route', 'timing', 'plan', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    args = parser.parse_args()
    route, timing, plan_path, out = (getattr(args, k).resolve() for k in ('route', 'timing', 'plan', 'output'))
    rr = verify(route/'assessment.json')
    tr = verify(timing/'assessment.json')
    assert tr['all_reported_setup_hold_electrical_checks_passed']
    assert tr['input_sha256'][str(route/'route.odb')] == sha(route/'route.odb')
    plan = json.loads(plan_path.read_text())
    masters = {c['master'] for c in plan['fixtures']}
    assert len(masters) == 40 and plan['pvt']['supply_v'] == 1.8
    loads = {m: max(c['external_load_pf'] for c in plan['fixtures'] if c['master'] == m) for m in masters}
    out.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__).resolve(), Path(OPENROAD), TECH, LEF, route/'assessment.json',
             route/'route.odb', timing/'assessment.json', plan_path]
    paths += [timing/f'route.{rc}.normalized.spef' for rc in ('nom', 'min', 'max')]
    pins = {str(p): sha(p) for p in paths}
    task = out/'inventory.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_db {route}/route.odb
set block [ord::get_db_block]
set output [open {out}/outputs.tsv w]
puts $output "instance\tmaster\tpin\tnet\tsinks\tports"
foreach inst [$block getInsts] {{
 foreach term [$inst getITerms] {{
  if {{[$term getIoType] ne {{OUTPUT}}}} {{continue}}
  set net [$term getNet]
  set sinks 0
  set ports 0
  set netname NULL
  if {{$net ne {{NULL}}}} {{
   set netname [$net getName]
   foreach sink [$net getITerms] {{
    if {{[$sink getIoType] in {{INPUT INOUT}}}} {{incr sinks}}
   }}
   set ports [llength [$net getBTerms]]
  }}
  puts $output "[$inst getName]\t[[$inst getMaster] getName]\t[[$term getMTerm] getName]\t$netname\t$sinks\t$ports"
 }}
}}
close $output
exit
''')
    assert run([OPENROAD, '-exit', task], out/'inventory.log') == 0
    with (out/'outputs.tsv').open() as stream:
        all_outputs = list(csv.DictReader(stream, delimiter='\t'))
    canonical_names = {}
    for row in all_outputs:
        # getName and SPEF NAME_MAP each carry one quoting layer. Preserve
        # literal backslashes by decoding once, never deleting all slashes.
        name = re.sub(r'\\(.)', r'\1', row['net'])
        assert name not in canonical_names or canonical_names[name] == row['net'], 'ambiguous escaped net name'
        canonical_names[name] = row['net']
        row['net_in_spef_namespace'] = name
    outputs = [r for r in all_outputs if r['master'] in masters]
    assert outputs and {r['master'] for r in outputs} == masters
    records = []
    for rc in ('nom', 'min', 'max'):
        caps = wire_caps(timing/f'route.{rc}.normalized.spef')
        groups = defaultdict(list)
        missing = []
        for row in outputs:
            used = int(row['sinks']) > 0 or int(row['ports']) > 0
            cap = caps.get(row['net_in_spef_namespace'])
            if used and cap is None:
                missing.append(row)
            groups[row['master']].append(dict(**row, used=used, reported_wire_cap_pf=cap))
        for master, rows in sorted(groups.items()):
            used = [r for r in rows if r['used']]
            known = [r['reported_wire_cap_pf'] for r in used if r['reported_wire_cap_pf'] is not None]
            records.append(dict(rc=rc, master=master, total_outputs=len(rows), used_outputs=len(used),
                unused_outputs=len(rows)-len(used), known_used_wire_caps=len(known),
                minimum_reported_wire_total_pf=min(known) if known else None,
                maximum_reported_wire_total_pf=max(known) if known else None,
                maximum_fixture_external_load_pf=loads[master],
                wire_total_exceeds_maximum_fixture=[r for r in used if r['reported_wire_cap_pf'] is not None and r['reported_wire_cap_pf'] > loads[master]],
                missing_used_spef=[r for r in missing if r['master'] == master]))
    for p, digest in pins.items():
        assert sha(p) == digest, p
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()}, records=records,
        combinational_master_types=len(masters), raw_min_max_wire_rc_sets=3,
        native_jobs_added=0, waveform_cases_excluded=0,
        decoded_name_collisions=0, case_sensitive_names_preserved=True,
        quoting_layers_removed_per_namespace=1,
        effective_load_enclosure_qualified=False, physical_timing_qualified=False,
        release_qualified=False, scope=__doc__))
    print('Audited wire-only loads for40combinational masters across3RC sets')


if __name__ == '__main__':
    main()
