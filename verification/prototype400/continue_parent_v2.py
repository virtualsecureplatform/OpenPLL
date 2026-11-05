#!/usr/bin/env python3
"""Continue a single prepared protection candidate through route/layout/geometry.

Each stage gets at most 12h including waiting. Stops on native failure; never
retries the same candidate or promotes raw RC into a physical simulation model.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha

PYTHON='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--power',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();power=a.power.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    scripts=Path(__file__).resolve().parent
    pinned={str(scripts/n):sha(scripts/n) for n in ('continue_parent_v2.py','route_parent_v6.py','check_parent_layout.py','check_parent_geometry.py')}
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),automatic_identical_retry=False,input_sha256=pinned))
    def state(stage,**fields):
        value=dict(state=stage,observed_utc=datetime.now(timezone.utc).isoformat(),controller_pid=os.getpid(),prototype_handoff_qualified=False,release_qualified=False,**fields)
        save(out/'status.json',value)
        root=ROOT/'build/timing400/prototype_001/status.json'
        record=json.loads(root.read_text());record['observed_utc']=value['observed_utc'];record['parent_pipeline']=dict(value,path=str(out/'status.json'))
        record['next']='Complete protected parent physical checks and fill-aware extraction before final-loaded KLU qualification.'
        save(root,record)
    def run(label,command):
        for path,digest in pinned.items():assert sha(path)==digest,path
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            state(label+'_running',child_pid=child.pid)
            try:code=child.wait(timeout=43200)
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
            assert code==0,(label,code)
    try:
        end=time.monotonic()+43200
        while not (power/'assessment.json').exists():
            if (power/'status.json').exists():assert json.loads((power/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<end
            state('waiting_for_protection_power');time.sleep(10)
        route=out/'route';layout=out/'layout';geometry=out/'geometry'
        run('route',[PYTHON,scripts/'route_parent_v6.py','--power',power,'--output',route])
        run('layout',[PYTHON,scripts/'check_parent_layout.py','--route',route,'--output',layout])
        checked=json.loads((layout/'assessment.json').read_text())
        assert checked['assembled_drc_pass'] and checked['assembled_lvs_pass'],'assembled layout nonpass'
        run('geometry',[PYTHON,scripts/'check_parent_geometry.py','--layout',layout,'--route',route,'--output',geometry])
        forming=json.loads((geometry/'forming_antenna/assessment.json').read_text())
        density=(geometry/'density.log').read_text()
        save(out/'assessment.json',dict(input_sha256=pinned,route_assessment=str(route/'assessment.json'),layout_assessment=str(layout/'assessment.json'),geometry_assessment=str(geometry/'assessment.json'),
             forming_antenna_violations=forming['violations'],stock_density_errors=density.count('***Error:'),
             prototype_handoff_qualified=False,release_qualified=False))
        state('parent_checks_terminal',forming_antenna_violations=forming['violations'],stock_density_errors=density.count('***Error:'))
    except BaseException as e:state('failed',reason=str(e));raise


if __name__=='__main__':main()
