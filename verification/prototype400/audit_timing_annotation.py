#!/usr/bin/env python3
"""Classify every unannotated timing driver from native database connectivity.

Open outputs and verified constant sources have no logical transition path.
This does not qualify power noise, cell admittance, final fill or full timing.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from common import ROOT, save, sha, verify
from repair_measured_antennas import tcl_word
sys.path.append(str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import lease
sys.path.append(str(ROOT / 'verification/timing400'))
from check_compact_mapping import TECH, LEF, OPENROAD


def drivers(text):
    blocks = re.findall(r'^Found (\d+) unannotated drivers\.\s*\n(.*?)^Found \d+ partially unannotated drivers\.', text, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('missing or ambiguous unannotated-driver report')
    count, body = blocks[0]
    rows = [line.strip() for line in body.splitlines() if line.strip()]
    if len(rows) != int(count) or len(set(rows)) != len(rows) or any('/' not in x for x in rows):
        raise ValueError('unannotated-driver report count/identity mismatch')
    return sorted(rows)


def block(text, kind, name):
    match = re.search(r'\b' + kind + r'\s*\(\s*"?' + re.escape(name) + r'"?\s*\)\s*\{', text)
    if not match:
        raise ValueError('library block missing: ' + kind + ' ' + name)
    depth = 1; quoted = escaped = False
    for i in range(match.end(), len(text)):
        c = text[i]
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return text[match.end():i]
    raise ValueError('truncated library block')


def constant_functions(text):
    cell = block(text, 'cell', 'sky130_fd_sc_hs__conb_1')
    result = {}
    for pin in ('HI', 'LO'):
        body = block(cell, 'pin', pin)
        direction = re.search(r'\bdirection\s*:\s*"output"\s*;', body)
        function = re.search(r'\bfunction\s*:\s*"([01])"\s*;', body)
        if not direction or not function:
            raise ValueError('tie output is not a verified constant')
        result[('sky130_fd_sc_hs__conb_1', pin)] = function[1]
    return result


def classify(row, constants):
    if row['other_drivers']:
        return 'unresolved_multiple_drivers'
    if row['sinks'] == 0 and row['ports'] == 0:
        return 'no_logical_fanout'
    if (row['master'], row['pin']) in constants:
        return 'verified_constant_source'
    return 'unresolved_active_signal'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'timing', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    a = p.parse_args(); route, timing, out = (x.resolve() for x in (a.route, a.timing, a.output))
    out.mkdir(parents=True, exist_ok=False); deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, release_qualified=False, **kw))

    try:
        report = json.loads((timing / 'assessment.json').read_text())
        verify(report['input_sha256']); verify(report['artifacts'])
        if report['input_sha256'].get(str(route / 'route.odb')) != sha(route / 'route.odb'):
            raise ValueError('timing/database identity mismatch')
        labels = None; logs = []
        for name in report['results']:
            log = timing / (name + '.log'); logs.append(log)
            current = drivers(log.read_text())
            if labels is not None and current != labels:
                raise ValueError('annotation inventory differs across supplied views')
            labels = current
        libraries = [Path(p) for p in report['input_sha256']
                     if Path(p).name.startswith('sky130_fd_sc_hs__') and Path(p).suffix == '.lib']
        if not libraries: raise ValueError('supplied timing library missing')
        constants = constant_functions(libraries[0].read_text())
        if any(constant_functions(lib.read_text()) != constants for lib in libraries[1:]):
            raise ValueError('supplied constant-source functions disagree')
        paths = [Path(__file__).resolve(), Path(sys.executable), Path(OPENROAD), TECH, LEF,
                 route / 'route.odb', timing / 'assessment.json', *logs, *libraries,
                 Path(__file__).with_name('common.py'), Path(__file__).with_name('repair_measured_antennas.py'),
                 ROOT / 'verification/signoff400/compiled_charge_v2.py', ROOT / 'verification/signoff400/resources.py']
        pins = {str(path): sha(path) for path in paths}
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        script = out / 'probe.tcl'
        text = f'read_lef {TECH}\nread_lef {LEF}\nread_db {route}/route.odb\nset_thread_count 2\nset block [ord::get_db_block]\nset f [open {out}/connectivity.tsv w]\n'
        for label in labels:
            inst, pin = label.rsplit('/', 1)
            text += f'''set inst [$block findInst {tcl_word(inst)}]
if {{$inst eq {{NULL}}}} {{error {{annotation instance missing}}}}
set term [$inst findITerm {tcl_word(pin)}]
if {{$term eq {{NULL}} || [$term getIoType] ne {{OUTPUT}}}} {{error {{annotation output pin missing}}}}
set net [$term getNet]
set sinks 0;set ports 0;set others 0;set netname {{-}}
if {{$net ne {{NULL}}}} {{
 set netname [$net getName]
 foreach other [$net getITerms] {{
  if {{$other eq $term}} {{continue}}
  if {{[$other getIoType] in {{INPUT INOUT}}}} {{incr sinks}} else {{incr others}}
 }}
 set ports [llength [$net getBTerms]]
}}
puts $f [join [list {tcl_word(label)} [[$inst getMaster] getName] {tcl_word(pin)} $netname $sinks $ports $others] "\t"]
'''
        text += 'close $f\nputs "ANNOTATION_CONNECTIVITY_COMPLETE"\nexit\n'; script.write_text(text)
        status('probing_native_database_connectivity')
        with lease(2, 4, deadline):
            execute([OPENROAD, '-no_init', '-exit', script], out / 'probe.log', deadline, 4)
        if 'ANNOTATION_CONNECTIVITY_COMPLETE' not in (out / 'probe.log').read_text():
            raise ValueError('annotation connectivity probe incomplete')
        rows = []; counts = Counter()
        for line in (out / 'connectivity.tsv').read_text().splitlines():
            label, master, pin, net, sinks, ports, others = line.split('\t')
            row = dict(driver=label, master=master, pin=pin, net=net, sinks=int(sinks), ports=int(ports), other_drivers=int(others))
            row['classification'] = classify(row, constants); rows.append(row); counts[row['classification']] += 1
        if sorted(r['driver'] for r in rows) != labels:
            raise ValueError('native probe did not account for every unannotated driver')
        verify(pins); save(out / 'drivers.json', rows)
        unresolved = sum(n for kind, n in counts.items() if kind.startswith('unresolved'))
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in out.iterdir() if path.is_file() and path.name != 'status.json'},
             unannotated_drivers=len(rows), classifications=dict(counts), unresolved_active_drivers=unresolved,
             all_unannotated_drivers_classified=unresolved == 0,
             active_transition_fanout_has_no_unresolved_annotation=unresolved == 0,
             power_noise_and_cell_admittance_qualified=False, final_fill_qualified=False,
             digital_timing_qualified=False, physical_timing_qualified=False, release_qualified=False))
        status('annotation_classification_complete', unresolved_active_drivers=unresolved)
    except BaseException as error:
        status('failed', reason=repr(error)); raise


if __name__ == '__main__': main()
