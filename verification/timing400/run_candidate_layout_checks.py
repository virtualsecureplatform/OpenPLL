#!/usr/bin/env python3
"""Run assembled GDS DRC and LVS extraction within one total12h budget."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time

from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from characterize_compact_propagation import PDK
from run_dco_qualification import ROOT,sha,save

MAGIC=Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
TOP='IntegerPLL_400MHz_CandidateTop'


def main():
    deadline=time.monotonic()+43200
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();assert not out.exists()
    base=ROOT/'build/timing400/release_001'
    streamed=base/'candidate_stream_002'
    assert verify(streamed/'assessment.json')['all_source_macro_geometry_and_labels_preserved']
    route=base/'candidate_detailed_route_002'
    private=ROOT/'build/timing450/pdk/sky130A'
    startup=private/'libs.tech/magic/sky130A.magicrc'
    hs=base/'compact_incremental_headroom_001/signoff/sky130_fd_sc_hs.canonical.spice'
    hd=PDK/'libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
    files=[Path(__file__).resolve(),MAGIC,Path(OPENROAD),startup,
           private/'libs.tech/magic/sky130A.tech',hs,hd,streamed/'assembly.gds',
           streamed/'assessment.json',route/'route.odb']
    pins={str(p):sha(p) for p in files}
    out.mkdir(parents=True)
    (out/'extraction').mkdir()
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(deadline-time.monotonic()),
        automatic_identical_retry=False,release_qualified=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,total_budget_s=43200,
        scope=__doc__,release_qualified=False))

    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_s=max(0,deadline-time.monotonic()),release_qualified=False,**fields))

    def execute(command,label,stdin=None):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('12h total layout-check budget exhausted')
        env=dict(os.environ,PDK_ROOT=str(private.parent))
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,command)),stdin=stdin,stdout=log,
                stderr=subprocess.STDOUT,cwd=out,env=env,start_new_session=True)
            status(label+'_running',native_pid=child.pid)
            try:
                code=child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
                status('timeout_inconclusive',stage=label)
                raise
        if code:
            status('native_nonpass',stage=label,exit_code=code)
            raise RuntimeError(label+' exited nonzero')
        for path,digest in pins.items():assert sha(path)==digest,path

    export=out/'powered_export.tcl'
    export.write_text(f'read_db {route}/route.odb\nwrite_verilog -include_pwr_gnd {out}/powered_top.v\n')
    execute([OPENROAD,'-no_init','-exit',export],'powered_export')
    drc=out/'drc.tcl'
    drc.write_text(f'''crashbackups stop
drc euclidean on
drc style drc(full)
drc on
snap internal
gds flatten true
gds read {streamed}/assembly.gds
load {TOP}
select top cell
expand
drc catchup
set errors [drc listall why]
set out [open {out}/drc_errors.rpt w]
set count 0
foreach {{why rectangles}} $errors {{
    puts $out $why
    foreach rect $rectangles {{incr count;puts $out $rect}}
}}
puts $out "MAGIC_DRC_RECTANGLES=$count"
close $out
puts "MAGIC_DRC_RECTANGLES=$count"
quit -noprompt
''')
    with drc.open() as stream:execute([MAGIC,'-dnull','-noconsole','-rcfile',startup],'drc',stream)
    extract=out/'extract.tcl'
    extract.write_text(f'''drc off
crashbackups disable
locking disable
gds read {streamed}/assembly.gds
readspice {hs}
readspice {hd}
load {TOP} -dereference
cd {out}/extraction
extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no adjust
extract
ext2spice lvs
ext2spice short resistor
ext2spice -o ../assembly.spice {TOP}.ext
feedback save ../feedback.txt
quit -noprompt
''')
    with extract.open() as stream:execute([MAGIC,'-dnull','-noconsole','-rcfile',startup],'extract',stream)
    status('drc_and_extraction_terminal',lvs_comparison_completed=False)
    save(out/'native_completion.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        drc_and_extraction_native_completed=True,lvs_comparison_completed=False,
        release_qualified=False,scope=__doc__))


if __name__=='__main__':
    main()
