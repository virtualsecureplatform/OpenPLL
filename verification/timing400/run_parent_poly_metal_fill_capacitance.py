#!/usr/bin/env python3
"""Extract a diagnostic capacitance network from the flat poly+metal-fill view.

Preserve floating capacitive nodes and device geometry. No node is grounded,
eliminated, fitted or adopted here. This is a CAD extraction, not a transient
analog run. Resistance, FOM/substrate coverage and model validation remain open.
"""
import argparse
from datetime import datetime,timezone
import json
import os
import signal
from pathlib import Path
import subprocess
import time
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['view','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();view=args.view.resolve();out=args.output.resolve();v=verify(view/'assessment.json')
    assert v['converted_metal_fill_purpose_layers_removed'] and v['converted_fill_material_footprints_preserved']
    assert v['drawing_and_fill_overlays_not_used']
    assert v['converted_poly_fill_purpose_removed'] and v['no_added_gate_contact_or_resistor_overlap']
    assert v['extraction_only_view'] and v['unique_parent_net_labels']==359 and v['manufacturing_gds_unchanged']
    owner=json.loads((view/'owner.json').read_text());deadline=owner['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    gds=view/'capacitance_view.gds';assert sha(gds)==v['artifacts'][str(gds)]
    out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(view/'owner.json'),total_budget_restarted=False,automatic_identical_retry=False))
    task=out/'extract.tcl';task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load {v['top']}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {out}/extraction_feedback.txt
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {out}/capacitance.spice {v['top']}.ext
puts "FILLED_CAPACITANCE_EXTRACTION_COMPLETE"
quit -noprompt
''')
    files=[Path(__file__).resolve(),MAGIC,startup,tech,task,view/'assessment.json',view/'owner.json',gds]
    pins={str(p):sha(p) for p in files};save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with task.open() as commands,(out/'extract.log').open('x') as log:
        child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
            stdout=log,stderr=subprocess.STDOUT,cwd=out,env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
        save(out/'status.json',dict(state='native_capacitance_extraction',native_pid=child.pid,native_analog_jobs_added=0,release_qualified=False))
        try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    for p,d in pins.items():assert sha(p)==d,p
    spice=out/'capacitance.spice';caps=0
    feedback=out/'extraction_feedback.txt'
    if spice.exists():
        with spice.open() as source:
            for line in source:
                if line[:1].upper()=='C':caps+=1
    success=code==0 and caps>0 and feedback.exists() and 'FILLED_CAPACITANCE_EXTRACTION_COMPLETE' in (out/'extract.log').read_text()
    save(out/'native_completion.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        exit_code=code,native_extraction_completed=success,capacitor_records=caps,floating_nodes_preserved=True,
        full_flattened_feedback_captured=feedback.exists(),converted_poly_fill_included=True,
        full_capacitance_coverage_qualified=False,resistance_included=False,model_adopted=False,release_qualified=False,scope=__doc__))
    save(out/'status.json',dict(state='raw_network_terminal' if success else 'native_nonpass',capacitor_records=caps,release_qualified=False))
    print('Raw capacitance extraction terminal:',code,'capacitors',caps,'qualified=False',flush=True)

if __name__=='__main__':main()
