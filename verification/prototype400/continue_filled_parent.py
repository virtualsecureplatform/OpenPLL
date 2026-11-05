#!/usr/bin/env python3
"""Check a single filled parent candidate, with exact topology and density audits."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha,verify
PYTHON='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fill','route','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();fill=a.fill.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    scripts=Path(__file__).resolve().parent;deadline=time.monotonic()+43200
    paths=[scripts/n for n in ('continue_filled_parent.py','check_parent_layout_v2.py','check_parent_geometry_v2.py','audit_parent_topology.py')]
    paths.append(ROOT/'verification/timing400/audit_assembled_density.py')
    pinned={str(p):sha(p) for p in paths}
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False,input_sha256=pinned))
    def state(stage,**fields):
        value=dict(state=stage,observed_utc=datetime.now(timezone.utc).isoformat(),controller_pid=os.getpid(),release_qualified=False,**fields)
        save(out/'status.json',value)
        root=ROOT/'build/timing400/prototype_001/status.json';record=json.loads(root.read_text())
        record['observed_utc']=value['observed_utc'];record['filled_parent_pipeline']=dict(value,path=str(out/'status.json'))
        save(root,record)
    def run(label,cmd):
        verify(pinned)
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            state(label+'_running',child_pid=child.pid)
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
            assert code==0,(label,code)
    try:
        while not (fill/'assessment.json').exists():
            if (fill/'status.json').exists():assert json.loads((fill/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;state('waiting_for_fill');time.sleep(10)
        report=json.loads((fill/'assessment.json').read_text());verify(report['input_sha256']);verify(report['artifacts'])
        layout=out/'layout';geo=out/'geometry';topology=out/'topology';density=out/'density_audit'
        run('layout',[PYTHON,scripts/'check_parent_layout_v2.py','--route',route,'--output',layout,'--gds',fill/'assembly.gds','--gds-receipt',fill/'assessment.json'])
        checked=json.loads((layout/'assessment.json').read_text())
        assert checked['assembled_drc_pass'] and checked['assembled_lvs_pass'],'filled assembly DRC/LVS nonpass'
        run('geometry',[PYTHON,scripts/'check_parent_geometry_v2.py','--layout',layout,'--route',route,'--output',geo])
        run('topology',[PYTHON,scripts/'audit_parent_topology.py','--stream',layout,'--route',route,'--output',topology])
        run('density_audit',[PYTHON,ROOT/'verification/timing400/audit_assembled_density.py','--density',geo,'--output',density])
        t=json.loads((topology/'assessment.json').read_text());d=json.loads((density/'assessment.json').read_text())
        ant=json.loads((geo/'forming_antenna/assessment.json').read_text())
        import re
        feedback=re.findall(r'^ASSEMBLED_ANTENNA_FEEDBACK=(\d+)$',(geo/'native_antenna.log').read_text(),re.M)
        assert len(feedback)==1
        geometry_pass=(t['complete_port_connectivity_screen_passed'] and d['stock_density_checks_passed'] and ant['violations']==0 and int(feedback[0])==0)
        save(out/'assessment.json',dict(input_sha256=pinned,filled_geometry_checks_pass=geometry_pass,
             assembled_drc_pass=checked['assembled_drc_pass'],assembled_lvs_pass=checked['assembled_lvs_pass'],
             complete_port_connectivity_screen_passed=t['complete_port_connectivity_screen_passed'],
             stock_density_checks_passed=d['stock_density_checks_passed'],forming_antenna_violations=ant['violations'],native_antenna_feedback=int(feedback[0]),
             filled_layout_assessment=str(layout/'assessment.json'),filled_geometry_assessment=str(geo/'assessment.json'),
             topology_assessment=str(topology/'assessment.json'),density_assessment=str(density/'assessment.json'),
             extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False))
        state('filled_geometry_pass' if geometry_pass else 'filled_geometry_nonpass')
    except BaseException as e:state('failed',reason=str(e));raise


if __name__=='__main__':main()
