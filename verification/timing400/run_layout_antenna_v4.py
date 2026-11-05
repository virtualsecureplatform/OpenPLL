#!/usr/bin/env python3
"""Run per-layer antenna checks using MOS-only gate extraction on exact GDS.

Uses the PDK's built-in ngspice(orig) style: MOSFET gates are sensitive;
pure diodes supply diffusion credit, without becoming artificial MOS gates.
Detailed debug output is retained for repair localization. Other process-rule
and extraction limitations remain explicit; this does not adopt a release.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from run_candidate_layout_checks_v2 import MAGIC, TOP
from run_dco_qualification import ROOT, sha, save


def main():
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--layout-evidence',required=True,type=Path)
    parser.add_argument('--gds',required=True,type=Path)
    parser.add_argument('--top',required=True)
    parser.add_argument('--original-layout-owner',required=True,type=Path)
    args = parser.parse_args()
    original_owner=args.original_layout_owner.resolve()
    original=json.loads(original_owner.read_text());deadline=original['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    base = ROOT/'build/timing400/release_001'
    audit = args.layout_evidence.resolve()
    layout = json.loads(audit.read_text())
    gds = args.gds.resolve()
    top = args.top
    assert top and all(c.isalnum() or c=='_' for c in top)
    if 'assembled_gds' in layout:
        assert layout['assembled_magic_drc_passed'] and layout['assembled_lvs_passed']
        assert gds == Path(layout['assembled_gds'])
        assert sha(gds) == layout['assembled_gds_sha256']
    else:
        assert layout['magic_drc_rectangles']==0 and layout['lvs_unique_match']
        assert sha(gds) == layout['sha256'][str(gds)]
    private = ROOT/'build/timing450/pdk/sky130A'
    startup = private/'libs.tech/magic/sky130A.magicrc'
    tech = private/'libs.tech/magic/sky130A.tech'
    method = private/'libs.tech/magic/check_antenna.py'
    assert 'antennacheck' in method.read_text()
    control = base/'antenna_diode_style_comparison_001/assessment.json'
    assert json.loads(control.read_text())['orig_known_controls_match_required_mos_only_reference']
    files = [original_owner,Path(__file__).resolve(), MAGIC, gds, audit, startup, tech, method,
        Path(__file__).with_name('run_candidate_layout_checks_v2.py'),
        Path(__file__).with_name('run_dco_qualification.py')]
    files += [control,base/'magic_antenna_rule_source_audit_001/source_manifest.json']
    pins = {str(p):sha(p) for p in files}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'extraction').mkdir()
    save(out/'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), total_budget_s=43200,
        deadline_uptime=deadline,original_owner=str(original_owner),total_budget_restarted=False,
        automatic_identical_retry=False))
    script = out/'antenna.tcl'
    script.write_text(f'''crashbackups stop
locking disable
drc off
snap internal
gds read {gds}
load {top} -dereference
select top cell
expand
cd {out}/extraction
extract style ngspice(orig)
extract do local
extract no all
extract all
puts "ASSEMBLED_ANTENNA_EXTRACTION_COMPLETE"
feedback save {out}/extraction_feedback.txt
feedback clear
puts "ASSEMBLED_ANTENNA_BEGIN"
antennacheck debug
antennacheck
set count [feedback count]
puts "ASSEMBLED_ANTENNA_FEEDBACK=$count"
feedback save {out}/antenna_feedback.txt
puts "ASSEMBLED_ANTENNA_END"
quit -noprompt
''')
    pins[str(script)] = sha(script)
    save(out/'input_manifest.json', dict(input_sha256=pins, scope=__doc__))
    env = dict(os.environ, PDK_ROOT=str(private.parent))
    with script.open() as commands, (out/'antenna.log').open('x') as log:
        child = subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],
            stdin=commands,stdout=log,stderr=subprocess.STDOUT,cwd=out,env=env)
        save(out/'status.json', dict(state='native_running', native_pid=child.pid,
            observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
        try:
            code = child.wait(timeout=max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False))
            return
    for path,digest in pins.items():
        assert sha(path) == digest, path
    save(out/'native_completion.json',dict(input_sha256=pins,exit_code=code,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ('status.json','owner.json')},
        elapsed_seconds=time.monotonic()-start,antenna_qualified=False,release_qualified=False,
        scope=__doc__))
    save(out/'status.json',dict(state='native_terminal',exit_code=code,release_qualified=False))
    print('MOS-only gate antenna method terminated; inspect extraction and rule coverage before qualification.')


if __name__ == '__main__':
    main()
