#!/usr/bin/env python3
"""Record actual HD/HS tie and diode exports in all installed RC styles.

Preflight two/four-terminal primitive versus foundry-wrapper schemas before a
full-layout corner extraction. This is native CAD only, not SPICE qualification.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pya
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT, sha, save


def main():
    base=ROOT/'build/timing400/release_001'
    out=base/'primitive_corner_exports_001'
    owner_path=base/'candidate_layout_checks_001/owner.json'
    owner=json.loads(owner_path.read_text())
    deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A'
    startup=private/'libs.tech/magic/sky130A.magicrc'
    tech=private/'libs.tech/magic/sky130A.tech'
    files=[Path(__file__).resolve(),Path(sys.executable),MAGIC,startup,tech,owner_path]
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    controls=[]
    for family in ['hs','hd']:
        path=private/f'libs.ref/sky130_fd_sc_{family}/gds/sky130_fd_sc_{family}.gds'
        files.append(path)
        library=pya.Layout()
        library.read(str(path))
        assert library.dbu==.001
        for kind,cell_name in [('tie','conb_1'),('diode','diode_2')]:
            master=f'sky130_fd_sc_{family}__{cell_name}'
            leaf=library.cell(master)
            assert leaf is not None
            layout=pya.Layout()
            layout.dbu=library.dbu
            top=layout.create_cell(f'CORNER_{family.upper()}_{kind.upper()}')
            top.copy_tree(leaf)
            gds=out/f'{family}_{kind}.gds'
            layout.write(str(gds))
            files.append(gds)
            controls.append((f'{family}_{kind}',gds,top.name,master))
    pins={str(p):sha(p) for p in files}
    observations={}
    for corner,style in [('min','ngspice(lrlc)'),('nom','ngspice(orig)'),('max','ngspice(hrhc)')]:
        observations[corner]={}
        for name,gds,top,master in controls:
            case=out/f'{corner}_{name}'
            case.mkdir()
            task=case/'extract.tcl'
            task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load {top}
extract style {style}
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {case}/feedback.txt
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {case}/control.spice {top}.ext
quit -noprompt
''')
            pins[str(task)]=sha(task)
            left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            assert left>0
            with task.open() as commands,(case/'extract.log').open('x') as log:
                child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
                    stdout=log,stderr=subprocess.STDOUT,cwd=case,
                    env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
                save(out/'status.json',dict(state='extracting_primitive_corner_control',corner=corner,case=name,
                    native_pid=child.pid,native_analog_jobs_added=0,release_qualified=False))
                try:
                    code=child.wait(timeout=left)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL)
                        child.wait()
                    save(out/'status.json',dict(state='timeout_inconclusive',corner=corner,case=name,release_qualified=False))
                    return
            assert code==0,(corner,name,code)
            native=(case/f'{top}.ext').read_text().splitlines()
            spice=(case/'control.spice').read_text().splitlines()
            observations[corner][name]=dict(master=master,style=style,native_exit_code=code,
                native_device_records=[line for line in native if line.startswith('device ')],
                exported_device_and_continuation_records=[line for line in spice if line[:1] in ['M','D','R','X','+']],
                feedback=(case/'feedback.txt').read_text())
    for path,digest in pins.items():
        assert sha(path)==digest,path
    save(out/'observations.json',observations)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_cad_controls_completed=12,raw_primitive_export_observations_only=True,
        rc_corners=['min','nom','max'],native_analog_jobs_added=0,
        full_layout_corner_extraction_complete=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='primitive_controls_terminal',release_qualified=False))
    print('Recorded12 actual HD/HS tie/diode corner exports; schema assessment remains separate.')


if __name__=='__main__':
    main()
