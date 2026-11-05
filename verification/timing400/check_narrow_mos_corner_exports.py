#!/usr/bin/env python3
"""Exercise the actual detector FF type with orig and nominal/min/max wrappers.

Check whether nominal wrapper selection changes the parsed wire-C matrix.
Keep ordinary/special MOS names distinct. This is a small native CAD control,
not a model equivalence test or a full-layout nominal wrapper extraction.
"""
from collections import Counter,defaultdict
from decimal import Decimal
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import pya
from audit_capacitance_corner_controls import native_devices
from audit_parent_capacitance_network import decimal_value
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';out=base/'narrow_mos_corner_exports_001'
    owner_path=base/'candidate_layout_checks_001/owner.json'
    deadline=json.loads(owner_path.read_text())['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc'
    tech=private/'libs.tech/magic/sky130A.tech';gds=private/'libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds'
    placed=base/'bbpd_internal_antenna_001/route.def';placement=placed.read_text()
    assert '- direction_ff sky130_fd_sc_hd__dfrtp_1 ' in placement and '- valid_ff sky130_fd_sc_hd__dfrtp_1 ' in placement
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_capacitance_corner_controls.py'),
        Path(__file__).with_name('audit_parent_capacitance_network.py'),MAGIC,rc,tech,gds,placed,owner_path]
    pins={str(p):sha(p) for p in paths};out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline,original_owner=str(owner_path),total_budget_restarted=False,automatic_identical_retry=False))
    lib=pya.Layout();lib.read(str(gds));assert lib.dbu==.001
    leaf=lib.cell('sky130_fd_sc_hd__dfrtp_1');assert leaf is not None
    layout=pya.Layout();layout.dbu=lib.dbu
    top=layout.create_cell('NARROW_MOS_CONTROL');top.copy_tree(leaf)
    isolated=out/'control.gds';layout.write(str(isolated));pins[str(isolated)]=sha(isolated)
    observations={};devices={};matrices={}
    for name,style in [('orig','ngspice(orig)'),('nom','ngspice()'),('min','ngspice(lrlc)'),('max','ngspice(hrhc)')]:
        case=out/name;case.mkdir();task=case/'extract.tcl'
        task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {isolated}
load NARROW_MOS_CONTROL
extract style {style}
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {case}/feedback.txt
ext2spice lvs
ext2spice cthresh 0
ext2spice -f ngspice -o {case}/control.spice NARROW_MOS_CONTROL.ext
puts "NARROW_MOS_CONTROL_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''')
        pins[str(task)]=sha(task)
        with (case/'extract.log').open('x') as log:
            child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(rc),str(task)],
                cwd=case,env=dict(os.environ,PDK_ROOT=str(private.parent)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'status.json',dict(state='native_cad_control_running',case=name,native_pid=child.pid,release_qualified=False,native_analog_jobs_added=0))
            try:code=child.wait(timeout=min(60,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',case=name,release_qualified=False));return
        assert code==0 and 'NARROW_MOS_CONTROL_COMPLETE' in (case/'extract.log').read_text()
        assert (case/'feedback.txt').read_text()==''
        ext=(case/'NARROW_MOS_CONTROL.ext').read_text().splitlines()
        native=[s for s in ext if s.startswith('device ')]
        devices[name]=native_devices(native)
        matrix=defaultdict(Decimal)
        for line in (case/'control.spice').read_text().splitlines():
            if line.startswith('C'):
                f=line.split();matrix[tuple(sorted(f[1:3]))]+=decimal_value(f[3])
        matrices[name]=dict(matrix)
        observations[name]=dict(native_exit_code=code,native_devices=native,positive_C_branches=sum(v>0 for v in matrix.values()),
            negative_C_branches=sum(v<0 for v in matrix.values()))
    assert matrices['orig']==matrices['nom']
    assert devices['nom']==devices['min']==devices['max']
    removed=devices['orig']-devices['nom'];added=devices['nom']-devices['orig']
    by_old={r[3:]:r for r in removed};by_new={r[3:]:r for r in added}
    assert by_old and by_old.keys()==by_new.keys()
    for key,old in by_old.items():
        new=by_new[key]
        assert old[2]=='sky130_fd_pr__nfet_01v8' and new[2]=='sky130_fd_pr__special_nfet_01v8'
        assert old[8]==new[8]=='72' and old[7]==new[7]=='30'
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'observations.json',observations)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        actual_detector_cell='sky130_fd_sc_hd__dfrtp_1',native_CAD_controls=4,
        native_devices_each=len(list(devices['nom'].elements())),
        special_nfet_name_changes_per_cell=sum(removed.values()),
        orig_and_nominal_wrapper_complete_capacitor_matrices_identical=True,
        all_three_wrapper_style_native_devices_identical=True,
        other_native_fields_preserved=True,all_feedback_empty=True,
        ordinary_and_special_models_aliased=False,electrical_equivalence_asserted=False,
        full_layout_nominal_wrapper_extraction_completed=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    save(out/'status.json',dict(state='native_control_assessment_complete',release_qualified=False))
    print('Detector FF: orig/nom wire-C matrices identical; wrapper devices match across3 RC styles; special names retained separately.')


if __name__=='__main__':main()
