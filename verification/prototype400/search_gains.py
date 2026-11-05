#!/usr/bin/env python3
"""Select one physically supported KI/KP pair across all five corners."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from common import PROFILE, spec, save, sha, verify
from run_loop import load_models


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',required=True,nargs=5,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();value=spec();started=time.monotonic()
    models={}
    for path in a.models:
        model=load_models(path.resolve(),False)
        if model['corner'] in models:raise ValueError('duplicate corner model')
        models[model['corner']]=path.resolve()
    if set(models)!=set(value['corners']):raise ValueError('all five corner models required')
    identities=[load_models(path,False)['candidate_physical_sha256'] for path in models.values()]
    if any(identity!=identities[0] for identity in identities):
        raise ValueError('all corners must describe the same physical candidate')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pins={str(path):sha(path) for path in [PROFILE,*models.values(),Path(__file__).resolve(),Path(__file__).with_name('run_loop.py')]}
    tried={};reports={};selected=None

    def evaluate(pair):
        nonlocal reports
        if pair in tried:return tried[pair]
        ki,kp=pair;group=out/f'ki{ki}_kp{kp}';group.mkdir()
        checked=[]
        for corner in value['corners']:
            verify(pins)
            directory=group/corner
            command=[sys.executable,str(Path(__file__).with_name('run_loop.py')),
                     '--models',str(models[corner]),'--output',str(directory),'--ki',str(ki),'--kp',str(kp)]
            with (group/(corner+'.log')).open('x') as log:
                code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                     timeout=max(.001,43200-(time.monotonic()-started))).returncode
            if code:raise RuntimeError('model or driver failure; stop gain expansion')
            report=json.loads((directory/'assessment.json').read_text())
            verify(report['input_sha256']);verify(report['artifacts'])
            checked.append(str(directory/'assessment.json'))
            if any(record['native_exit']!=0 for record in report['records']):
                raise RuntimeError('uncovered model or runtime failure; characterize before continuing')
            if not report['whole_pll_qualification_pass']:
                tried[pair]=False;reports[pair]=checked;return False
        tried[pair]=True;reports[pair]=checked;return True

    # Preserve the requested starting point; cached results avoid identical reruns.
    evaluate(tuple(value['gain_search']['first']))
    for pair in ((ki,kp) for ki in value['gain_search']['ki'] for kp in value['gain_search']['kp']):
        if evaluate(pair):selected=pair;break
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         selected_gain=dict(ki=selected[0],kp=selected[1]) if selected else None,
         trials=[dict(ki=pair[0],kp=pair[1],passed=passed,corner_reports=reports[pair])
                 for pair,passed in tried.items()],
         whole_pll_qualification_pass=selected is not None,
         prototype_handoff_qualified=False,release_qualified=False))
    print('Selected gain',selected)


if __name__=='__main__':main()
