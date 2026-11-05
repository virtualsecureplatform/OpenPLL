#!/usr/bin/env python3
"""Compare diagnostic default mode with installed extractor on24 CAD cases.

Four independent physical controls span floating poly/metal, an HS NAND and the
actual narrow-device detector FF. Compare full parsed C matrices, native device
statements and feedback at min/nom/max. This is baseline agreement on controls,
not full-layout binary equivalence or spatial capacitor-placement qualification.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from audit_parent_capacitance_network import decimal_value
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def matrix(path):
    result=defaultdict(Decimal)
    for line in path.read_text().splitlines():
        if line.startswith('C'):
            f=line.split();result[tuple(sorted(f[1:3]))]+=decimal_value(f[3])
    return {key:value for key,value in result.items() if value!=0}


def devices(path):
    return Counter(' '.join(s.split()) for s in path.read_text().splitlines() if s.startswith('device '))


def main():
    base=ROOT/'build/timing400/release_001';build=base/'magic_cap_clip_build_002'
    b=verify(build/'assessment.json');assert b['diagnostic_clip_build_completed']
    isolated=ROOT/'build/timing400/magic_cap_clip_623_002/bin/magic';assert isolated.is_file()
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    cases=[('floating_metal',base/'fill_capacitance_control_001/drawing_purpose/control.gds','FILL_CAP_CONTROL'),
        ('floating_poly',base/'lower_fill_capacitance_controls_001/poly_drawing/control.gds','LOWER_FILL_CONTROL'),
        ('HS_NAND',base/'capacitance_corner_controls_001/nand2_2.gds','CAP_CORNER_NAND'),
        ('HD_narrow_FF',base/'narrow_mos_corner_exports_001/control.gds','NARROW_MOS_CONTROL')]
    out=base/'magic_cap_clip_default_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),build/'assessment.json',
        isolated,MAGIC,rc,tech,owner_path,*[gds for name,gds,top in cases]]
    pins={str(p):sha(p) for p in paths}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    env=dict(os.environ,PDK_ROOT=str(private.parent));env.pop('OPENPLL_CAP_CLIP_INTERNAL',None)
    results=[]
    for corner,style in [('min','ngspice(lrlc)'),('nom','ngspice()'),('max','ngspice(hrhc)')]:
        for name,gds,top in cases:
            records={}
            for tool,binary in [('installed',MAGIC),('isolated',isolated)]:
                target=out/f'{corner}_{name}_{tool}';target.mkdir()
                task=target/'extract.tcl';task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {gds}
load {top}
extract style {style}
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {target}/feedback.txt
ext2spice lvs
ext2spice cthresh 0
ext2spice -f ngspice -o {target}/control.spice {top}.ext
puts "ISOLATED_STOCK_CONTROL_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''')
                pins[str(task)]=sha(task)
                with (target/'extract.log').open('x') as log:
                    child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=target,
                        stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                    save(out/'status.json',dict(state='native_baseline_control_running',corner=corner,case=name,tool=tool,
                        native_pid=child.pid,native_analog_jobs_added=0,release_qualified=False))
                    try:code=child.wait(timeout=min(60,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=10)
                        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                        save(out/'status.json',dict(state='timeout_inconclusive',case=name,corner=corner,tool=tool,release_qualified=False));return
                assert code==0 and 'ISOLATED_STOCK_CONTROL_COMPLETE' in (target/'extract.log').read_text(),(name,tool,code)
                records[tool]=dict(matrix=matrix(target/'control.spice'),devices=devices(target/(top+'.ext')),
                    feedback=(target/'feedback.txt').read_text())
            a,b=records['installed'],records['isolated']
            assert a['matrix']==b['matrix'] and a['devices']==b['devices'] and a['feedback']==b['feedback'],(name,corner)
            results.append(dict(case=name,corner=corner,exact_parsed_C_matrix_equal=True,
                exact_native_device_statements_equal=True,feedback_equal=True,
                nonzero_C_pairs=len(a['matrix']),native_devices=sum(a['devices'].values())))
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'comparison.json',results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs=24,physical_controls=4,RC_corners=['min','nom','max'],
        installed_and_isolated_C_devices_feedback_equal=True,
        full_layout_binary_equivalence_proven=False,C_location_method_qualified=False,
        installed_tool_replaced=False,golden_Xyce_changed=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='native_baseline_controls_passed',release_qualified=False))
    print('24 native stock controls pass: C, native devices and feedback equal across3 RC corners. Spatial method/full-layout equivalence remain unqualified.')


if __name__=='__main__':main()
