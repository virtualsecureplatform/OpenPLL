#!/usr/bin/env python3
"""Search one KI/KP pair across 15 identity-qualified PVT models in parallel."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time

from common_v2 import PROFILE, spec, save, sha, verify, source_pins
from loop_v2 import load_models


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',required=True,nargs=15,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();value=spec();started=time.monotonic()
    models={}
    for path in a.models:
        model=load_models(path.resolve(),False)
        key=(model['corner'],model['temperature_c'])
        if key in models: raise ValueError('duplicate PVT model')
        models[key]=path.resolve()
    expected={(c,t) for c in value['corners'] for t in value['temperatures_c']}
    if set(models)!=expected: raise ValueError('all 15 PVT models required')
    identities=[load_models(path,False)['candidate_physical_sha256'] for path in models.values()]
    if any(identity!=identities[0] for identity in identities):
        raise ValueError('all PVT models must describe the same physical candidate')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pins={str(path):sha(path) for path in [PROFILE,*models.values(),Path(__file__).resolve(),Path(__file__).with_name('loop_v2.py')]}
    tried={};reports={};selected=None
    def evaluate(pair):
        if pair in tried:return tried[pair]
        ki,kp=pair;group=out/f'ki{ki}_kp{kp}';group.mkdir()
        def point(key):
            verify(pins)
            c,t=key;directory=group/f'{c}_{t}C'
            command=[sys.executable,str(Path(__file__).with_name('loop_v2.py')),
                     '--models',str(models[key]),'--output',str(directory),'--ki',str(ki),'--kp',str(kp)]
            with (group/f'{c}_{t}C.log').open('x') as log:
                code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                     timeout=max(.001,43200-(time.monotonic()-started))).returncode
            if code:raise RuntimeError('model or driver failure; stop gain expansion')
            path=directory/'assessment.json';report=json.loads(path.read_text())
            verify(report['input_sha256']);verify(report['artifacts'])
            if any(record['native_exit']!=0 for record in report['records']):
                raise RuntimeError('uncovered model or runtime failure; characterize before continuing')
            return path,report
        with ThreadPoolExecutor(max_workers=15) as pool:
            completed=list(pool.map(point,sorted(models)))
        reports[pair]=[str(path) for path,_ in completed]
        tried[pair]=all(r['whole_pll_qualification_pass'] for _,r in completed)
        return tried[pair]
    evaluate(tuple(value['gain_search']['first']))
    for pair in ((ki,kp) for ki in value['gain_search']['ki'] for kp in value['gain_search']['kp']):
        if evaluate(pair):selected=pair;break
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         candidate_source_sha256=source_pins(),candidate_physical_sha256=identities[0],profile_sha256=sha(PROFILE),
         artifacts={path:sha(path) for paths in reports.values() for path in paths},
         selected_gain=dict(ki=selected[0],kp=selected[1]) if selected else None,
         trials=[dict(ki=pair[0],kp=pair[1],passed=passed,pvt_reports=reports[pair]) for pair,passed in tried.items()],
         whole_pll_qualification_pass=selected is not None, macro_handoff_qualified=False,release_qualified=False))
    print('Selected gain',selected)


if __name__=='__main__':main()
