#!/usr/bin/env python3
"""Exercise installed capacitance corners on isolated fill and MOS controls.

Reuse known physical controls and one actual HS standard-cell GDS. Record raw
capacitance and native/exported device statements; no transient analog engine,
full-layout enclosure, interpolation or timing qualification is inferred.
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
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT, sha, save


def main():
    base=ROOT/'build/timing400/release_001'
    out=base/'capacitance_corner_controls_001'
    lower=base/'lower_fill_capacitance_controls_001'
    metal=base/'fill_capacitance_control_001'
    verify(lower/'assessment.json')
    verify(metal/'assessment.json')
    owner_path=base/'candidate_layout_checks_001/owner.json'
    owner=json.loads(owner_path.read_text())
    deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A'
    startup=private/'libs.tech/magic/sky130A.magicrc'
    tech=private/'libs.tech/magic/sky130A.tech'
    cell_gds=private/'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
    paths=[Path(__file__).resolve(),Path(sys.executable),MAGIC,startup,tech,cell_gds,owner_path,
        lower/'assessment.json',metal/'assessment.json']
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    library=pya.Layout()
    library.read(str(cell_gds))
    leaf=library.cell('sky130_fd_sc_hs__nand2_2')
    assert leaf is not None and library.dbu==.001
    isolated=pya.Layout()
    isolated.dbu=library.dbu
    top=isolated.create_cell('CAP_CORNER_NAND')
    top.copy_tree(leaf)
    isolated_gds=out/'nand2_2.gds'
    isolated.write(str(isolated_gds))
    controls=[('m1_baseline',lower/'no_tile/control.gds','LOWER_FILL_CONTROL'),
        ('floating_poly',lower/'poly_drawing/control.gds','LOWER_FILL_CONTROL'),
        ('p_bulk_surface',lower/'ohmic_p_tap/control.gds','LOWER_FILL_CONTROL'),
        ('n_bulk_surface',lower/'nwell_ohmic_n_tap/control.gds','LOWER_FILL_CONTROL'),
        ('floating_metal',metal/'drawing_purpose/control.gds','FILL_CAP_CONTROL'),
        ('nand2_2',isolated_gds,'CAP_CORNER_NAND')]
    paths += [p for _,p,_ in controls]
    pins={str(p):sha(p) for p in paths}
    results={}
    for corner,style in [('min','ngspice(lrlc)'),('nom','ngspice(orig)'),('max','ngspice(hrhc)')]:
        results[corner]={}
        for name,gds,top_name in controls:
            case=out/f'{corner}_{name}'
            case.mkdir()
            task=case/'extract.tcl'
            task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load {top_name}
extract style {style}
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {case}/feedback.txt
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {case}/control.spice {top_name}.ext
quit -noprompt
''')
            pins[str(task)]=sha(task)
            left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            assert left>0
            with task.open() as commands,(case/'extract.log').open('x') as log:
                child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
                    stdout=log,stderr=subprocess.STDOUT,cwd=case,
                    env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
                save(out/'status.json',dict(state='extracting_corner_control',corner=corner,case=name,
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
            lines=(case/'control.spice').read_text().splitlines()
            native=(case/(top_name+'.ext')).read_text().splitlines()
            results[corner][name]=dict(style=style,native_exit_code=code,
                capacitor_records=[line for line in lines if line.startswith('C')],
                native_device_records=[line for line in native if line.startswith('device ')],
                exported_device_records=[line for line in lines if line[:1] in ['M','D','R','X']],
                feedback=(case/'feedback.txt').read_text())
    for p,digest in pins.items():
        assert sha(p)==digest,p
    save(out/'observations.json',results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['status.json','owner.json']},
        native_cad_controls_completed=18,rc_corners=['min','nom','max'],
        raw_corner_and_device_observations_only=True,full_layout_capacitance_qualified=False,
        material_enclosure_qualified=False,native_analog_jobs_added=0,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='corner_controls_terminal',release_qualified=False))
    print('Completed18 installed corner controls, including actual NAND geometry; raw data retained for independent audit.')


if __name__=='__main__':
    main()
