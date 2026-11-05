#!/usr/bin/env python3
"""Finish topology/density audits of existing passing native filled-layout checks."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from common import ROOT,save,sha,verify
from status_store import update_root
PYTHON='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous-closure','route','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prev=a.previous_closure.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads((prev/'owner.json').read_text());started=original.get('budget_started_utc',original['started_utc'])
    left=43200-max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds());assert left>0
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),budget_started_utc=started,original_owner=str(prev/'owner.json'),wall_limit_s=43200,automatic_identical_retry=False))
    def status(state,**kw):
        v=dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw)
        save(out/'status.json',v);update_root('filled_parent_pipeline',dict(v,path=str(out/'status.json')))
    try:
        checked=json.loads((prev/'layout/assessment.json').read_text());verify(checked['input_sha256']);verify(checked['artifacts'])
        g=json.loads((prev/'geometry/assessment.json').read_text());verify(g['input_sha256']);verify(g['artifacts'])
        assert checked['assembled_drc_pass'] and checked['assembled_lvs_pass'] and g['density_native_exit']==0
        for name in ('layout','geometry'):(out/name).symlink_to(prev/name,target_is_directory=True)
        scripts=Path(__file__).resolve().parent
        inputs=[Path(__file__).resolve(),scripts/'audit_parent_topology_v2.py',ROOT/'verification/timing400/audit_assembled_density.py',prev/'layout/assessment.json',prev/'geometry/assessment.json',prev/'geometry/native_completion.json',prev/'owner.json',route/'assessment.json']
        pins={str(p):sha(p) for p in inputs}
        for label,cmd in [('topology',[PYTHON,scripts/'audit_parent_topology_v2.py','--stream',out/'layout','--route',route,'--output',out/'topology']),('density',[PYTHON,ROOT/'verification/timing400/audit_assembled_density.py','--density',out/'geometry','--output',out/'density_audit'])]:
            verify(pins)
            with (out/(label+'.log')).open('x') as log:
                status(label+'_audit_running')
                result=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=left)
                assert result.returncode==0,(label,result.returncode)
        topo=json.loads((out/'topology/assessment.json').read_text());den=json.loads((out/'density_audit/assessment.json').read_text())
        ant=json.loads((out/'geometry/forming_antenna/assessment.json').read_text())
        feedback=re.findall(r'^ASSEMBLED_ANTENNA_FEEDBACK=(\d+)$',(out/'geometry/native_antenna.log').read_text(),re.M);assert len(feedback)==1
        passed=topo['complete_port_connectivity_screen_passed'] and den['stock_density_checks_passed'] and ant['violations']==0 and feedback==['0']
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,filled_geometry_checks_pass=passed,assembled_drc_pass=True,assembled_lvs_pass=True,
             complete_port_connectivity_screen_passed=topo['complete_port_connectivity_screen_passed'],stock_density_checks_passed=den['stock_density_checks_passed'],
             forming_antenna_violations=ant['violations'],native_antenna_feedback=int(feedback[0]),
             filled_layout_assessment=str(out/'layout/assessment.json'),filled_geometry_assessment=str(out/'geometry/assessment.json'),
             topology_assessment=str(out/'topology/assessment.json'),density_assessment=str(out/'density_audit/assessment.json'),
             native_layout_checks_repeated=False,extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False))
        status('filled_geometry_pass' if passed else 'filled_geometry_nonpass')
    except BaseException as e:status('failed',reason=repr(e));raise


if __name__=='__main__':main()
