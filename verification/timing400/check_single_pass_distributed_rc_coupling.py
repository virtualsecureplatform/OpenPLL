#!/usr/bin/env python3
"""Observe RC export with a real buffer driver and an explicit floating tile.

This also corrects the first driven control's conflicting port indices.
The optional tile uses a unique explicit named port; the original buffer X
port is the only port on the extended conductor. A previous native signal11 followed duplicate conductor port definitions;
causation was not independently established.
This version disables automatic resistance extraction and invokes extresist
once, because extract do resistance already runs that stage on this version.
This differs from the stopped wire-only control: it has native MOS drivers,
uses the established nonzero resistance tolerance, and records native failures.
No full-layout or timing qualification follows from successful extraction.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import pya
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT, sha, save


def main():
    base=ROOT/'build/timing400/release_001'
    prior=base/'distributed_rc_coupling_controls_001'
    owner_path=base/'candidate_layout_checks_001/owner.json'
    deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    # Preserve the stopped experiment; do not retry its inputs or assert a cause.
    for key in ['runner_pid','native_pid']:
        for source in ['owner.json','status.json']:
            data=json.loads((prior/source).read_text())
            if key in data:assert not (Path('/proc')/str(data[key])).exists()
    out=base/'driven_distributed_rc_coupling_controls_004'
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,
        automatic_identical_retry=False,prior_control=str(prior),prior_control_completion_observed=False))
    private=ROOT/'build/timing450/pdk/sky130A'
    rc=private/'libs.tech/magic/sky130A.magicrc'
    tech=private/'libs.tech/magic/sky130A.tech'
    gds=private/'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
    lef=private/'libs.ref/sky130_fd_sc_hs/lef/sky130_fd_sc_hs.lef'
    paths=[Path(__file__).resolve(),MAGIC,rc,tech,gds,lef,owner_path]
    paths += [p for p in prior.rglob('*') if p.is_file()]
    pins={str(p):sha(p) for p in paths}
    lib=pya.Layout();lib.read(str(gds));assert lib.dbu==.001
    leaf=lib.cell('sky130_fd_sc_hs__buf_1');assert leaf is not None
    layout=pya.Layout();layout.dbu=lib.dbu
    top=layout.create_cell('DRIVEN_COUPLING_CONTROL');top.copy_tree(leaf)
    # Extend only the documented X LI pin. M1 tile has no contact to this LI.
    top.shapes(layout.layer(67,20)).insert(pya.Box(1660,2500,81660,2800))
    top.shapes(layout.layer(68,20)).insert(pya.Box(20000,1000,60000,4000))
    control=out/'control.gds';layout.write(str(control));pins[str(control)]=sha(control)
    results={}
    for name,ported in [('floating_tile',False),('ported_tile',True)]:
        case=out/name;case.mkdir()
        extra='box values 40um 2um 40.2um 2.2um\nlabel AGG center m1\nport AGG make 21\nport AGG class input\n' if ported else ''
        task=case/'extract.tcl'
        task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {control}
load DRIVEN_COUPLING_CONTROL
select top cell
{extra}extract style ngspice()
extract do unique
extract do capacitance
extract do coupling
extract no resistance
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist off
ext2spice -f ngspice -o {case}/lumped.spice DRIVEN_COUPLING_CONTROL.ext
extresist tolerance 0.0001
extresist threshold 0
extresist simplify off
extresist all
feedback save {case}/feedback.txt
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -f ngspice -o {case}/distributed.spice DRIVEN_COUPLING_CONTROL.ext
puts "DRIVEN_COUPLING_CONTROL_COMPLETE"
}} error]}} {{puts stderr $error; exit 1}}
exit 0
''')
        pins[str(task)]=sha(task)
        with (case/'extract.log').open('x') as log:
            child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(rc),str(task)],
                cwd=case,env=dict(os.environ,PDK_ROOT=str(private.parent)),stdout=log,
                stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'status.json',dict(state='native_control_running',case=name,native_pid=child.pid,
                native_analog_jobs_added=0,release_qualified=False))
            timeout=False
            try:code=child.wait(timeout=min(60,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except subprocess.TimeoutExpired:
                timeout=True;os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                code=child.returncode
        log=(case/'extract.log').read_text()
        complete=code==0 and 'DRIVEN_COUPLING_CONTROL_COMPLETE' in log
        results[name]=dict(native_exit_code=code,timeout_inconclusive=timeout,completed=complete,
            ports_on_tile=ported,export_files_exist={p:(case/p).exists() for p in ['lumped.spice','distributed.spice']})
        if not complete:break
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'observations.json',results)
    complete=len(results)==2 and all(r['completed'] for r in results.values())
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        two_native_controls_completed=complete,results=results,coupling_preservation_assessed=False,
        full_distributed_rc_qualified=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    save(out/'status.json',dict(state='raw_controls_terminal' if complete else 'control_nonpass',release_qualified=False))
    print(json.dumps(results))


if __name__=='__main__':main()
