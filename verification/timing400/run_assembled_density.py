#!/usr/bin/env python3
"""Run the installed PDK density workflow against exact assembled GDS.

The stock workflow reports 700um stepped windows and global density. Its
geometry extent, edge weighting and applicable integration region must be
audited before treating a clean result as final density qualification.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from run_candidate_layout_checks_v2 import MAGIC, TOP
from run_dco_qualification import ROOT, sha, save


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base = ROOT/'build/timing400/release_001'
    audit = base/'candidate_assembled_layout_audit_001/assessment.json'
    data = json.loads(audit.read_text())
    assert data['assembled_magic_drc_passed'] and data['assembled_lvs_passed']
    gds = Path(data['assembled_gds'])
    assert sha(gds) == data['assembled_gds_sha256']
    private = ROOT/'build/timing450/pdk/sky130A'
    source = private/'libs.tech/magic/check_density.py'
    paths = [Path(__file__).resolve(), MAGIC, gds, audit, source,
        private/'libs.tech/magic/sky130A.tech',private/'libs.tech/magic/sky130A.magicrc',
        Path(__file__).with_name('run_candidate_layout_checks_v2.py'),
        Path(__file__).with_name('run_dco_qualification.py')]
    pins = {str(p):sha(p) for p in paths}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/(TOP+'.gds')).symlink_to(gds)
    save(out/'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(),total_budget_s=43200,
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(43200-(time.monotonic()-started)),
        automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    env = dict(os.environ,PDK_ROOT=str(private.parent),PDK='sky130A',
               PATH=str(MAGIC.parent)+os.pathsep+os.environ.get('PATH',''))
    with (out/'density.log').open('x') as log:
        child = subprocess.Popen(['/usr/bin/python3',str(source),TOP+'.gds'],
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=out,env=env,
            start_new_session=True)
        save(out/'status.json',dict(state='native_running',native_pid=child.pid,
            observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
        try:
            code = child.wait(timeout=max(1,43200-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            # The stock script launches Magic; stop the whole isolated group.
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False))
            return
    for path,digest in pins.items():
        assert sha(path) == digest, path
    save(out/'native_completion.json',dict(input_sha256=pins,exit_code=code,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('owner.json','status.json')},
        elapsed_seconds=time.monotonic()-started,density_qualified=False,
        release_qualified=False,scope=__doc__))
    save(out/'status.json',dict(state='native_terminal',exit_code=code,release_qualified=False))
    print('Stock assembled density workflow terminated; inspect raw coverage and reported violations.')


if __name__ == '__main__':
    main()
