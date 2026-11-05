#!/usr/bin/env python3
"""Observe whether installed extresist preserves explicit coupling on controls.

Annotate two ends of a known M4 wire as ports. Compare a floating M5 tile with
the same tile given explicit ports. Preserve before/after SPICE and all native
feedback; no claim about distributed full-layout RC or model adoption.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    original=base/'fill_capacitance_control_001'
    verify(original/'assessment.json')
    owner_path=base/'candidate_layout_checks_001/owner.json'
    owner=json.loads(owner_path.read_text());deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'distributed_rc_coupling_controls_001';out.mkdir(exist_ok=False)
    private=ROOT/'build/timing450/pdk/sky130A'
    startup=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    gds=original/'drawing_purpose/control.gds'
    files=[Path(__file__).resolve(),MAGIC,startup,tech,gds,original/'assessment.json',owner_path]
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    results={}
    for name,driven in [('floating_tile',False),('ported_tile',True)]:
        case=out/name;case.mkdir()
        extra='''box values 40.05um 50.05um 40.25um 50.25um
label AGG_SRC center m5
port make 2
port class input
box values 59.75um 50.05um 59.95um 50.25um
label AGG_DST center m5
port make 3
port class output
''' if driven else ''
        task=case/'extract.tcl'
        task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {gds}
load FILL_CAP_CONTROL
box values 10.05um 50.05um 10.25um 50.25um
label SRC center m4
port make 0
port class input
box values 89.75um 50.05um 89.95um 50.25um
label DST center m4
port make 1
port class output
{extra}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2spice cthresh 0
ext2spice subcircuit off
ext2spice extresist off
ext2spice -o {case}/lumped.spice FILL_CAP_CONTROL.ext
extresist simplify off
extresist threshold 0
extresist tolerance 0
extresist ignore VSUBS
extresist all
feedback save {case}/feedback.txt
ext2spice lvs
ext2spice cthresh 0
ext2spice subcircuit off
ext2spice extresist on
ext2spice -f ngspice -o {case}/distributed.spice FILL_CAP_CONTROL.ext
puts "DISTRIBUTED_COUPLING_CONTROL_COMPLETE"
quit -noprompt
''')
        pins[str(task)]=sha(task)
        with task.open() as commands,(case/'extract.log').open('x') as log:
            child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
                stdout=log,stderr=subprocess.STDOUT,cwd=case,
                env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
            save(out/'status.json',dict(state='native_control_running',case=name,native_pid=child.pid,
                native_analog_jobs_added=0,release_qualified=False))
            try:code=child.wait(timeout=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',case=name,release_qualified=False));return
        log=(case/'extract.log').read_text()
        assert code==0 and 'DISTRIBUTED_COUPLING_CONTROL_COMPLETE' in log
        results[name]=dict(native_exit_code=code,
            lumped_records=[line for line in (case/'lumped.spice').read_text().splitlines() if line[:1] in ['C','R']],
            distributed_records=[line for line in (case/'distributed.spice').read_text().splitlines() if line[:1] in ['C','R']],
            feedback=(case/'feedback.txt').read_text(),ports_on_tile=driven)
    for p,digest in pins.items():assert sha(p)==digest,p
    save(out/'observations.json',results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['status.json','owner.json']},
        native_cad_controls_completed=2,raw_before_after_observations_only=True,
        coupling_or_charge_preservation_assessed=False,full_distributed_rc_qualified=False,
        native_analog_jobs_added=0,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='raw_controls_terminal',release_qualified=False))
    print('Recorded two ported-wire extresist controls; coupling preservation requires assessment.')


if __name__=='__main__':main()
