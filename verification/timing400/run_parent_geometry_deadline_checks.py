#!/usr/bin/env python3
"""Run independent parent geometry checks under the original layout deadline."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['route','stream','original-layout-owner','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();route=args.route.resolve();stream=args.stream.resolve();out=args.output.resolve()
    original=args.original_layout_owner.resolve();owner=json.loads(original.read_text());deadline=owner['deadline_uptime']
    verify(route/'assessment.json');verify(stream/'assessment.json');assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    scripts=Path(__file__).resolve().parent
    commands={
        'topology':[sys.executable,str(scripts/'audit_assembled_macro_port_topology.py'),'--route',str(route),'--stream',str(stream),'--output',str(out/'topology')],
        'antenna':[sys.executable,str(scripts/'check_forming_antenna_geometry_v2.py'),'--gds',str(stream/'assembly.gds'),'--top','IntegerPLL_400MHz_CandidateTop','--output',str(out/'antenna')]}
    paths=[Path(__file__).resolve(),Path(sys.executable),original,route/'assessment.json',route/'route.def',stream/'assessment.json',stream/'assembly.gds',
        scripts/'audit_assembled_macro_port_topology.py',scripts/'check_forming_antenna_geometry_v2.py']
    pins={str(p):sha(p) for p in paths};out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(original),total_budget_restarted=False,automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,commands=commands,release_qualified=False))
    children={};logs={};timeout=False
    try:
        for name,command in commands.items():
            logs[name]=(out/(name+'.log')).open('x')
            children[name]=subprocess.Popen(command,stdout=logs[name],stderr=subprocess.STDOUT,start_new_session=True)
        save(out/'status.json',dict(state='geometry_checks_running',child_pids={n:c.pid for n,c in children.items()},release_qualified=False))
        while any(c.poll() is None for c in children.values()):
            left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            if left<=0:timeout=True;break
            time.sleep(min(5,left))
    finally:
        for child in children.values():
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        for log in logs.values():log.close()
    for path,digest in pins.items():assert sha(path)==digest,path
    codes={n:c.returncode for n,c in children.items()}
    state='timeout_inconclusive' if timeout else ('native_terminal' if len(codes)==2 and all(c==0 for c in codes.values()) else 'native_nonpass')
    save(out/'native_completion.json',dict(input_sha256=pins,exit_codes=codes,state=state,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ('status.json','native_completion.json')},
        release_qualified=False,adopted=False))
    save(out/'status.json',dict(state=state,exit_codes=codes,release_qualified=False))
    print(state,codes,flush=True)

if __name__=='__main__':main()
