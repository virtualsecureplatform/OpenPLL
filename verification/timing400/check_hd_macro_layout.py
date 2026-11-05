#!/usr/bin/env python3
"""Stream an isolated HD macro and check its exact GDS with Magic and Netgen.

Shares the repair's original total 12h deadline. This is geometry/connectivity
evidence only; antenna, formation coverage and analog behavior are separate.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from check_compact_clock_tree import verify
from characterize_compact_propagation import PDK
from run_candidate_layout_checks_v2 import MAGIC
from run_candidate_lvs_v2 import NETGEN
from run_dco_qualification import ROOT,sha,save
from stream_candidate_assembly_v5 import STREAM

PYTHON='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    args=parser.parse_args();route=args.route.resolve()
    receipt=verify(route/'assessment.json');top=receipt['top']
    assert top=='IntegerPLL_BBPD' and receipt['router_drc_violations']==0
    original=json.loads((route/'owner.json').read_text())
    deadline=original['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    library=PDK/'libs.ref/sky130_fd_sc_hd'
    private=ROOT/'build/timing450/pdk/sky130A'
    tech=library/'techlef/sky130_fd_sc_hd__nom.tlef'
    lef=library/'lef/sky130_fd_sc_hd.lef'
    gds=library/'gds/sky130_fd_sc_hd.gds'
    spice=library/'spice/sky130_fd_sc_hd.spice'
    startup=private/'libs.tech/magic/sky130A.magicrc'
    setup=private/'libs.tech/netgen/sky130A_setup.tcl'
    paths=[Path(__file__).resolve(),Path(PYTHON),Path(STREAM),Path(MAGIC),Path(NETGEN),
        route/'assessment.json',route/'route.odb',route/'route.def',route/'powered.v',route/'owner.json',
        tech,lef,gds,spice,startup,setup,private/'libs.tech/magic/sky130A.tech']
    maps=[private/'libs.tech/klayout/tech'/('sky130A.'+s) for s in ('lyt','lyp','map')];paths+=maps
    pins={str(p):sha(p) for p in paths}
    out=route/'signoff';out.mkdir(parents=True,exist_ok=False);(out/'extraction').mkdir()
    save(out/'owner.json',dict(runner_pid=os.getpid(),deadline_uptime=deadline,
        original_owner=str(route/'owner.json'),started_utc=datetime.now(timezone.utc).isoformat(),automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    env=dict(os.environ,PDK_ROOT=str(private.parent))

    def execute(command,label,stdin=None):
        left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:raise TimeoutError('original 12h check deadline')
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,command)),stdin=stdin,stdout=log,stderr=subprocess.STDOUT,
                cwd=out,env=env,start_new_session=True)
            save(out/'status.json',dict(state=label+'_running',native_pid=child.pid,remaining_s=left,release_qualified=False))
            try:code=child.wait(timeout=left)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));raise
        assert code==0,(label,code)

    execute([PYTHON,STREAM,'-o',out/'route.gds','-t',top,'-T',maps[0],'-P',maps[1],'-M',maps[2],
        '-l',tech,'-l',lef,'-w',gds,route/'route.def'],'stream')
    drc=out/'drc.tcl';drc.write_text(f'''crashbackups stop
drc euclidean on
drc style drc(full)
drc on
snap internal
gds flatten true
gds read {out}/route.gds
load {top}
select top cell
expand
drc catchup
set f [open {out}/drc_errors.rpt w]
set count 0
foreach {{why boxes}} [drc listall why] {{
 puts $f $why
 foreach box $boxes {{incr count;puts $f $box}}
}}
puts $f "MAGIC_DRC_RECTANGLES=$count"
close $f
puts "MAGIC_DRC_RECTANGLES=$count"
quit -noprompt
''')
    with drc.open() as commands:execute([MAGIC,'-dnull','-noconsole','-rcfile',startup],'drc',commands)
    extract=out/'extract.tcl';extract.write_text(f'''drc off
crashbackups stop
locking disable
gds read {out}/route.gds
readspice {spice}
load {top} -dereference
cd {out}/extraction
extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no adjust
extract
ext2spice lvs
ext2spice short resistor
ext2spice -o ../{top}.spice {top}.ext
quit -noprompt
''')
    with extract.open() as commands:execute([MAGIC,'-dnull','-noconsole','-rcfile',startup],'extract',commands)
    compare=out/'compare.tcl';compare.write_text(f'''readnet spice {out}/{top}.spice 1
readnet spice {spice} 2
readnet verilog {route}/powered.v 2
lvs {{{top} 1}} {{{top} 2}} {setup} {out}/compare.log -json
quit
''')
    execute([NETGEN,'-batch','source',compare],'netgen')
    rectangles=int(re.search(r'MAGIC_DRC_RECTANGLES=(\d+)',(out/'drc_errors.rpt').read_text())[1])
    log=(out/'compare.log').read_text()
    passed='Final result: Circuits match uniquely.' in log and 'Property errors were found' not in log and 'Top level cell failed pin matching' not in log
    data=json.loads((out/'compare.json').read_text());assert data[-1]['name']==[top,top]
    passed=passed and all(not row.get('badnets') and not row.get('badelements') for row in data)
    for path,digest in pins.items():assert sha(path)==digest,path
    artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ('owner.json','status.json')}
    save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        sha256={**pins,**artifacts},magic_drc_rectangles=rectangles,lvs_unique_match=passed,
        top_pins=len(data[-1]['pins'][0]),antenna_qualified=False,analog_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='layout_checks_terminal',release_qualified=False))
    print(json.dumps(dict(magic_drc_rectangles=rectangles,lvs_unique_match=passed)))


if __name__=='__main__':main()
