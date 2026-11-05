#!/usr/bin/env python3
"""Measure stock lower fill, conductive poly and ohmic-surface reference controls.

These are CAD extraction controls. Doped-tap rectangles are electrical reference
surfaces, not claims that dummy active fill carries those implant masks.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
import pya
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';owner_path=base/'candidate_layout_checks_001/owner.json'
    deadline=json.loads(owner_path.read_text())['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    paths=[Path(__file__).resolve(),Path(os.sys.executable),MAGIC,startup,tech,owner_path];pins={str(p):sha(p) for p in paths}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,total_budget_restarted=False,original_owner=str(owner_path)))
    cases=[('no_tile',[],False),('poly_fill',[(66,99)],False),('poly_drawing',[(66,20)],False),
        ('fom_fill',[(65,99)],False),('bare_active',[(65,20)],False),('ohmic_p_tap',[(65,44),(94,20)],False),
        ('nwell_no_tile',[],True),('nwell_fom_fill',[(65,99)],True),('nwell_ohmic_n_tap',[(65,44),(93,44)],True)]
    results={}
    for name,rectangles,nwell in cases:
        case=out/name;case.mkdir();layout=pya.Layout();layout.dbu=.001;top=layout.create_cell('LOWER_FILL_CONTROL')
        top.shapes(layout.layer(68,20)).insert(pya.Box(10000,50000,90000,50140))
        top.shapes(layout.layer(68,5)).insert(pya.Text('SIG',pya.Trans(50000,50070)))
        if nwell:
            top.shapes(layout.layer(64,20)).insert(pya.Box(0,0,100000,100000))
            top.shapes(layout.layer(64,5)).insert(pya.Text('VPWR',pya.Trans(20000,20000)))
        for key in rectangles:top.shapes(layout.layer(*key)).insert(pya.Box(40000,42000,60000,58000))
        gds=case/'control.gds';layout.write(str(gds));task=case/'extract.tcl'
        task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load LOWER_FILL_CONTROL
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {case}/feedback.txt
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {case}/control.spice LOWER_FILL_CONTROL.ext
quit -noprompt
''')
        pins[str(gds)]=sha(gds);pins[str(task)]=sha(task)
        with task.open() as commands,(case/'extract.log').open('x') as log:
            child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
                stdout=log,stderr=subprocess.STDOUT,cwd=case,env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
            save(out/'status.json',dict(state='extracting_control',case=name,native_pid=child.pid,release_qualified=False))
            try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
            except subprocess.TimeoutExpired:
                child.terminate();child.wait(timeout=10);save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
        assert code==0
        spice=case/'control.spice';lines=spice.read_text().splitlines()
        results[name]=dict(native_exit_code=code,capacitor_records=[line for line in lines if line[:1]=='C'],
            active_device_records=[line for line in lines if line[:1] in ['M','D','R','X']],feedback=(case/'feedback.txt').read_text())
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['assessment.json','status.json']},
        cases=results,reference_surfaces_are_not_manufacturing_changes=True,full_fill_electrical_coverage_qualified=False,
        numerical_enclosure_not_inferred=True,native_analog_jobs_added=0,release_qualified=False,scope=__doc__))
    save(out/'status.json',dict(state='controls_terminal',release_qualified=False));print(json.dumps(results,indent=2),flush=True)

if __name__=='__main__':main()
