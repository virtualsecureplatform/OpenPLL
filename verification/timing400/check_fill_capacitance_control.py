#!/usr/bin/env python3
"""Check whether stock extraction includes an actual floating metal-fill tile.

Three physical controls share one M4 signal wire: no tile, an M5 fill-purpose
tile, and the same tile on the normal M5 drawing purpose. These are extraction
controls, not an adopted electrical model or a transient analog simulation.
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--original-layout-owner',type=Path,required=True)
    args=parser.parse_args();owner_path=args.original_layout_owner.resolve();deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    files=[Path(__file__).resolve(),Path(os.sys.executable),MAGIC,startup,tech,owner_path]
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        total_budget_restarted=False,original_owner=str(owner_path),automatic_identical_retry=False))
    cases={}
    for name,datatype in [('no_tile',None),('fill_purpose',99),('drawing_purpose',20)]:
        case=out/name;case.mkdir()
        layout=pya.Layout();layout.dbu=.001;top=layout.create_cell('FILL_CAP_CONTROL')
        top.shapes(layout.layer(71,20)).insert(pya.Box(10000,50000,90000,50300))
        top.shapes(layout.layer(71,5)).insert(pya.Text('SIG',pya.Trans(50000,50150)))
        if datatype is not None:top.shapes(layout.layer(72,datatype)).insert(pya.Box(40000,42000,60000,58000))
        gds=case/'control.gds';layout.write(str(gds))
        task=case/'extract.tcl';task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load FILL_CAP_CONTROL
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract all
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {case}/control.spice FILL_CAP_CONTROL.ext
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
        spice=case/'control.spice';assert spice.exists()
        caps=[line for line in spice.read_text().splitlines() if line[:1].upper()=='C']
        cases[name]=dict(capacitor_records=caps,spice=str(spice),native_exit=code)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['status.json','assessment.json']},
        controls=cases,native_analog_jobs_added=0,electrical_extraction_qualified=False,release_qualified=False,scope=__doc__))
    save(out/'status.json',dict(state='controls_terminal',release_qualified=False))
    print(json.dumps(cases,indent=2),flush=True)

if __name__=='__main__':main()
