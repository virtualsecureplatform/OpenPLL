#!/usr/bin/env python3
"""Compare assembled extraction with powered repaired-macro candidate netlists; share layout deadline."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time

from characterize_compact_propagation import PDK
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

NETGEN=Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')
TOP='IntegerPLL_400MHz_CandidateTop'
DCO='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout-checks',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    layout,out=args.layout_checks.resolve(),args.output.resolve()
    assert not out.exists()
    owner=json.loads((layout/'owner.json').read_text())
    deadline=owner['deadline_uptime']
    private=ROOT/'build/timing450/pdk/sky130A'
    base=ROOT/'build/timing400/release_001'
    digital=base/'compact_internal_antenna_001/signoff'
    dco=ROOT/'openlane'/DCO/'runs/c1fine_range_001/final'
    sampled=ROOT/'build/timing450/interface_characterization/bbpd_sampled'
    hs=digital/'sky130_fd_sc_hs.canonical.spice'
    hd=PDK/'libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
    setup=private/'libs.tech/netgen/sky130A_setup.tcl'
    verilog=[digital/'powered.v',dco/'pnl'/(DCO+'.pnl.v'),
             base/'bbpd_internal_antenna_001/powered.v',layout/'powered_top.v']
    assert json.loads((dco/'metrics.json').read_text())['design__lvs_error__count']==0
    assert verify(base/'bbpd_internal_antenna_001/signoff/assessment.json')['lvs_unique_match']
    files=[Path(__file__).resolve(),NETGEN,hs,hd,setup,*verilog,
           digital/'assessment.json',dco/'metrics.json',base/'bbpd_internal_antenna_001/signoff/assessment.json',
           layout/'owner.json',layout/'input_manifest.json']
    pins={str(p):sha(p) for p in files}
    out.mkdir(parents=True)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_layout_owner=str(layout/'owner.json'),deadline_uptime=deadline,
        automatic_identical_retry=False,release_qualified=False))

    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,**fields))

    def remaining():
        left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:
            status('timeout_inconclusive')
            raise TimeoutError('original layout12h deadline exhausted')
        return left

    while not (layout/'native_completion.json').exists():
        remaining()
        process=Path('/proc')/str(owner['runner_pid'])
        if not process.exists():
            status('layout_producer_terminal_without_completion')
            return
        argv=(process/'cmdline').read_bytes().decode()
        script=Path(owner['runner_script'])
        assert script.name=='run_candidate_layout_checks_v2.py' and str(script) in argv
        manifest=json.loads((layout/'input_manifest.json').read_text())
        assert sha(script)==manifest['input_sha256'][str(script)]
        status('waiting_for_layout_extraction')
        time.sleep(min(30,remaining()))
    verify(layout/'native_completion.json')
    pins[str(layout/'native_completion.json')]=sha(layout/'native_completion.json')
    pins[str(layout/'assembly.spice')]=sha(layout/'assembly.spice')
    for path,digest in pins.items():assert sha(path)==digest,path
    compare=out/'compare.tcl'
    commands=[f'readnet spice {layout}/assembly.spice 1',f'readnet spice {hs} 2',f'readnet spice {hd} 2']
    commands += [f'readnet verilog {v} 2' for v in verilog]
    commands += [f'lvs {{{TOP} 1}} {{{TOP} 2}} {setup} {out}/compare.log -json','quit']
    compare.write_text('\n'.join(commands)+'\n')
    pins[str(compare)]=sha(compare)
    save(out/'input_manifest.json',dict(input_sha256=pins,original_layout_deadline_uptime=deadline,
        total_budget_restarted=False,release_qualified=False))
    with (out/'native.log').open('x') as log:
        child=subprocess.Popen([str(NETGEN),'-batch','source',str(compare)],
            stdout=log,stderr=subprocess.STDOUT,cwd=out,
            env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
        status('netgen_running',native_pid=child.pid)
        try:
            code=child.wait(timeout=remaining())
        except (subprocess.TimeoutExpired,TimeoutError):
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            status('timeout_inconclusive')
            return
    text=(out/'compare.log').read_text() if (out/'compare.log').exists() else ''
    records=json.loads((out/'compare.json').read_text()) if (out/'compare.json').exists() else []
    unique=(code==0 and 'Final result: Circuits match uniquely.' in text
            and 'Property errors were found' not in text and 'Top level cell failed pin matching' not in text)
    root=[r for r in records if r.get('name')==[TOP,TOP]]
    complete=bool(len(root)==1 and records[-1] is root[0]
                  and all(not r.get('badnets') and not r.get('badelements') for r in records))
    macros_expanded=True
    for name in ('IntegerPLL_AcquiringCore',DCO,'IntegerPLL_BBPD'):
        matching=[r for r in records if r.get('name')==[name,name]]
        macros_expanded &= bool(len(matching)==1 and all(sum(int(n) for _,n in side)>0 for side in matching[0]['devices']))
    for path,digest in pins.items():assert sha(path)==digest,path
    passed=unique and complete and macros_expanded
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        native_exit_code=code,all_three_macros_expanded=bool(macros_expanded),
        final_unique_match=unique,all_hierarchy_mismatch_lists_empty=complete,
        assembled_lvs_passed=passed,full_assembled_drc_passed=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    status('lvs_pass' if passed else 'lvs_nonpass')


if __name__=='__main__':
    main()
