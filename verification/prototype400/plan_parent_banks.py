#!/usr/bin/env python3
"""Build an exact compiled placement plan; CAD application validates geometry."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from common import ROOT,save,sha
sys.path.append(str(ROOT/'verification/signoff400'))
from compiled_charge import execute
from resources import lease


def run(frame,localization,output):
    frame,loc,out=(Path(p).resolve() for p in (frame,localization,output))
    out.mkdir(parents=True,exist_ok=False)
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    sources=[Path(__file__).resolve(),ROOT/'tools/parent_bank_planner/main.cpp',ROOT/'tools/charge_compiler/json.hpp',
             frame/'assessment.json',loc/'assessment.json',loc/'records.json']
    pins={str(p):sha(p) for p in sources}
    f=json.loads((frame/'assessment.json').read_text());r=json.loads((loc/'assessment.json').read_text())
    assert f['assembly_frame_pass'] and r['violations_with_macro_port']==r['violations']
    assert r['input_sha256'][str(frame/'assessment.json')]==sha(frame/'assessment.json')
    records=json.loads((loc/'records.json').read_text());by_net={}
    for row in records:
        for port in row['macro_ports']:
            if port['net'] not in by_net or port['instance']=='oscillator':by_net[port['net']]=port
    if any(any(c in name for c in '{}\\\r\n') for name in by_net):raise ValueError('unsupported Tcl net name')
    cfg=dict(macro_boxes=list(f['macro_bboxes_dbu'].values()),
             targets=[dict(net=n,point=by_net[n]['point']) for n in sorted(by_net)])
    save(out/'config.json',cfg)
    try:
        with lease(2,4,deadline):
            save(out/'status.json',dict(state='building_compiled_planner',release_qualified=False))
            binary=out/'planner'
            command=['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',str(sources[1]),'-o',str(binary)]
            execute(command,out/'build.log',deadline,4)
            t=time.monotonic();execute([binary,out/'config.json'],out/'plan.json',deadline,4);planning_s=time.monotonic()-t
            plan=json.loads((out/'plan.json').read_text())
            if pins!={str(p):sha(p) for p in sources}:raise ValueError('plan input changed')
            save(out/'assessment.json',dict(input_sha256=pins,
                artifacts={str(p):sha(p) for p in (binary,out/'config.json',out/'plan.json')},build_command=command,
                nets=len(plan),compiled_search_seconds=planning_s,
                elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
                cad_geometry_validated=False,release_qualified=False))
            save(out/'status.json',dict(state='candidate_plan_complete_pending_cad_validation',release_qualified=False))
    except BaseException as error:
        save(out/'status.json',dict(state='failed',reason=repr(error),release_qualified=False));raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('frame','localization','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.frame,a.localization,a.output)


if __name__=='__main__':main()
