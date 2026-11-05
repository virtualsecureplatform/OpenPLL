#!/usr/bin/env python3
"""Export the retained active DCO .ext without resistance backannotation.

Read existing extraction evidence; do not rerun layout extraction or edit live
simulation inputs. Preserve both the old0.01fF threshold and full positive C
export so threshold pruning is separated from RC backannotation differences.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    source=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')
    rc=pdk/'libs.tech/magic/sky130A.magicrc';tech=pdk/'libs.tech/magic/sky130A.tech'
    provenance=json.loads((source/'provenance.json').read_text())['files']
    assert sha(tech)==provenance[str(tech)] and sha(rc)==provenance[str(rc)]
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'active_dco_lumped_capacitance_export_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    ext=source/(top+'.ext')
    task=out/'export.tcl';task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
ext2spice lvs
ext2spice extresist off
ext2spice cthresh 0.01
ext2spice -f ngspice -o {out}/lumped_threshold001.spice {ext}
ext2spice cthresh 0
ext2spice -f ngspice -o {out}/lumped_full.spice {ext}
puts "ACTIVE_DCO_LUMPED_EXPORT_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''')
    paths=[Path(__file__).resolve(),MAGIC,rc,tech,task,ext,source/(top+'.res.ext'),
        source/(top+'.rcx.spice'),source/(top+'.reduced.spice'),source/'extract.tcl',source/'provenance.json',owner_path]
    pins={str(p):sha(p) for p in paths}
    with (out/'export.log').open('x') as log:
        child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=out,
            env=dict(os.environ,PDK_ROOT=str(pdk.parent)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=child.wait(timeout=min(120,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    assert code==0 and 'ACTIVE_DCO_LUMPED_EXPORT_COMPLETE' in (out/'export.log').read_text()
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},native_exit_code=code,
        existing_ext_exported_with_resistance_backannotation_disabled=True,
        old_threshold_and_full_C_exports_retained=True,live_simulation_inputs_modified=False,
        layout_extractions_added=0,native_analog_jobs_added=0,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Retained DCO .ext exported without RC backannotation at0.01fF and0fF; active inputs unchanged.')


if __name__=='__main__':main()
