"""Run one new raw mux2_4 propagation point; no timing-view qualification."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from assess_compact_propagation_campaign import assess
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True,type=Path);args=parser.parse_args()
    plan=json.loads(args.plan.read_text());out=args.plan.parent/'run_001';out.mkdir(exist_ok=False)
    pins=dict(plan['input_sha256']);pins[str(args.plan.resolve())]=sha(args.plan)
    reference=json.loads(Path(plan['reference_plan']).read_text())
    for name,digest in reference['input_sha256'].items():
        if name.startswith('/opt/pdk/') or name=='/opt/xyce/bin/Xyce':pins[name]=digest
    for name,digest in pins.items():
        if sha(Path(name))!=digest:raise ValueError('case input changed: '+name)
    deadline=plan['deadline_uptime'];remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    if remaining<300:raise TimeoutError('native assessment reserve unavailable')
    command=['/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',str(out/'batch'),str(args.plan.parent/'batch.cir')]
    with (out/'run.log').open('x') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=out,
             env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        birth=Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        save(out/'launch.json',dict(pid=child.pid,birth=birth,command=command,deadline_uptime=deadline,
             input_sha256=pins,automatic_identical_retry=False,release_qualified=False))
        try:code=child.wait(timeout=remaining-300)
        finally:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:child.kill();child.wait()
    if code:raise RuntimeError('native mux2_4 characterization failed')
    assess(plan,pins,out,deadline)


if __name__=='__main__':main()
