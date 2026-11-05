#!/usr/bin/env python3
"""After the current route completes, audit logic and streamed digital layout."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import ROOT, save, sha, verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--route',required=True,type=Path)
    p.add_argument('--gold-json',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();route=a.route.resolve();out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
         deadline_uptime=deadline,wall_limit_s=43200,automatic_identical_retry=False))
    def status(state,**extra):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
             prototype_handoff_qualified=False,**extra))
    status('waiting_for_current_route')
    while not (route/'assessment.json').exists():
        if (route/'status.json').exists():
            current=json.loads((route/'status.json').read_text())
            if current['state']=='physical_build_nonpass':
                status('stopped_after_route_nonpass');return
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            status('timeout_inconclusive');return
        time.sleep(10)
    receipt=json.loads((route/'assessment.json').read_text())
    verify(receipt['input_sha256']);verify(receipt['artifacts'])
    stages=[('route_equivalence',[sys.executable,Path(__file__).with_name('check_route_equivalence_v2.py'),
             '--route',route,'--gold-json',a.gold_json.resolve(),'--output',out/'equivalence']),
            ('digital_layout',[sys.executable,Path(__file__).with_name('check_layout.py'),'--route',route])]
    receipts=[]
    for name,command in stages:
        status(name+'_running')
        with (out/(name+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,command)),cwd=ROOT,stdout=log,
                                   stderr=subprocess.STDOUT,start_new_session=True)
            save(out/(name+'_launch.json'),dict(pid=child.pid,command=list(map(str,command))))
            try:
                code=child.wait(timeout=max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                status('timeout_inconclusive',stage=name);return
        receipts.append(dict(stage=name,native_exit=code))
        if code:
            status('stage_nonpass',stage=name,native_exit=code);return
    audit=json.loads((route/'signoff/assessment.json').read_text())
    save(out/'assessment.json',dict(native_receipts=receipts,
         route_equivalence=str(out/'equivalence/assessment.json'),
         route_equivalence_sha256=sha(out/'equivalence/assessment.json'),
         digital_layout_assessment=str(route/'signoff/assessment.json'),
         digital_layout_assessment_sha256=sha(route/'signoff/assessment.json'),
         digital_layout_pass=audit['diagnostic_physical_pass'],
         assembled_macro_qualified=False,prototype_handoff_qualified=False))
    status('digital_physical_checks_completed',digital_layout_pass=audit['diagnostic_physical_pass'])


if __name__=='__main__':main()
