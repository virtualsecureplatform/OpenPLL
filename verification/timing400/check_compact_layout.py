#!/usr/bin/env python3
"""Run the existing independent layout audit in a fresh compact build root.

The historical audit remains immutable. Only its build-root argument and
fresh-output handling are adapted in a retained, reviewable runner copy.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    started=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    args=parser.parse_args();root=args.route.resolve()
    receipt=verify(root/'assessment.json')
    assert receipt['restricted_master_inventory_passed'] and receipt['nominal_signal_rc_extracted']
    assert not (root/'signoff').exists(),'refuse to overwrite audit evidence'
    old=ROOT/'verification/timing450';source=old/'signoff.py'
    text=source.read_text()
    replacements={
        "    parser.add_argument('--library',": "    parser.add_argument('--root', required=True)\n    parser.add_argument('--library',",
        "    root = REPO / 'build/timing450' / args.library": "    root = Path(args.root).resolve()",
        '    signoff.mkdir(exist_ok=True)': '    signoff.mkdir(exist_ok=False)',
        "    (signoff / 'assessment.json').unlink(missing_ok=True)\n": ''}
    for before,after in replacements.items():
        assert text.count(before)==1,before
        text=text.replace(before,after)
    runner=root/'layout_audit_runner';runner.mkdir(exist_ok=False)
    script=runner/'signoff.py';script.write_text(text)
    helper=runner/'hs_views.py';helper.write_bytes((old/'hs_views.py').read_bytes())
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_clock_tree.py').resolve(),
           source,old/'run.py',old/'hs_views.py',script,helper,
           root/'assessment.json',root/'route.odb',root/'route.def']
    pins={str(p):sha(p) for p in files}
    env=dict(os.environ,PYTHONPATH=str(old)+os.pathsep+os.environ.get('PYTHONPATH',''))
    command=[sys.executable,str(script),'--root',str(root),'--library','hs',
             '--pdk-root',str(ROOT/'build/timing450/pdk')]
    with (runner/'driver.log').open('x') as log:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(runner/'launch.json',dict(pid=child.pid,command=command,input_sha256=pins,per_check_timeout_s=43200))
        try:
            code=child.wait(timeout=max(0.001,43200-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(runner/'timeout.json',dict(inconclusive=True,release_qualified=False))
            raise
    assert code==0,(runner/'driver.log').read_text()[-2000:]
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    result=json.loads((root/'signoff/assessment.json').read_text())
    save(runner/'completion.json',dict(input_sha256=pins,audit=str(root/'signoff/assessment.json'),
        audit_sha256=sha(root/'signoff/assessment.json'),
        diagnostic_physical_pass=result['diagnostic_physical_pass'],release_qualified=False,
        scope='Independent streamed-GDS Magic DRC, layout LVS, antenna and PG connectivity. Density, EM/IR, physical noise and nominal15PVT timing remain separate gates.'))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
