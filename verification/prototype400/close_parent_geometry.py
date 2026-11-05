#!/usr/bin/env python3
"""Reconcile exact-candidate filled layout, antenna, topology and density checks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from common import save, sha, verify, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('layout', 'geometry', 'route', 'frame', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    a = parser.parse_args()
    layout, geometry, route, frame, out = (
        getattr(a, n).resolve() for n in ('layout', 'geometry', 'route', 'frame', 'output'))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + 43200
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             release_qualified=False, **kw))

    def read(folder):
        report = json.loads((folder / 'assessment.json').read_text())
        verify(report['input_sha256']); verify(report.get('artifacts', {}))
        return report

    try:
        for folder in (layout, geometry):
            while not (folder / 'assessment.json').exists():
                if (folder / 'status.json').exists():
                    assert json.loads((folder / 'status.json').read_text())['state'] != 'failed', str(folder)
                assert time.monotonic() < deadline, 'whole-check deadline exhausted'
                status('waiting_for_native_checks', path=str(folder)); time.sleep(10)
        checked, measured = read(layout), read(geometry)
        assert checked['assembled_drc_pass'] and checked['assembled_lvs_pass']
        assert measured['raw_checks_completed'] and measured['density_native_exit'] == 0
        for path in (layout / 'assembly.gds', route / 'route.odb'):
            assert measured['input_sha256'].get(str(path)) == sha(path), str(path)
        for name, folder in (('layout', layout), ('geometry', geometry)):
            (out / name).symlink_to(folder, target_is_directory=True)
        scripts = Path(__file__).resolve().parent
        topology = scripts / 'audit_parent_topology_v3.py'
        density = ROOT / 'verification/timing400/audit_assembled_density.py'
        pins = {str(p): sha(p) for p in (Path(__file__).resolve(), Path(sys.executable), topology,
                density, layout / 'assessment.json', geometry / 'assessment.json',
                route / 'assessment.json', frame / 'assessment.json')}
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        commands = (
            ('topology', [sys.executable, topology, '--stream', layout, '--route', route,
                          '--frame', frame, '--output', out / 'topology']),
            ('density', [sys.executable, density, '--density', geometry, '--output', out / 'density_audit']))
        for label, cmd in commands:
            verify(pins)
            with (out / (label + '.log')).open('x') as log:
                child = subprocess.Popen(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
                status(label + '_running', native_pid=child.pid)
                try:
                    code = child.wait(timeout=max(.01, deadline - time.monotonic()))
                except BaseException:
                    os.killpg(child.pid, signal.SIGTERM)
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
                    raise
                assert code == 0, (label, code)
        topo, den = read(out / 'topology'), read(out / 'density_audit')
        ant = read(geometry / 'forming_antenna')
        feedback = re.findall(r'^ASSEMBLED_ANTENNA_FEEDBACK=(\d+)$',
                              (geometry / 'native_antenna.log').read_text(), re.M)
        assert len(feedback) == 1
        passed = (topo['complete_port_connectivity_screen_passed'] and den['stock_density_checks_passed']
                  and ant['violations'] == 0 and feedback == ['0'])
        verify(pins)
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in (out / 'topology/assessment.json', out / 'density_audit/assessment.json')},
             filled_geometry_checks_pass=passed, assembled_drc_pass=True, assembled_lvs_pass=True,
             complete_port_connectivity_screen_passed=topo['complete_port_connectivity_screen_passed'],
             stock_density_checks_passed=den['stock_density_checks_passed'],
             forming_antenna_violations=ant['violations'], native_antenna_feedback=int(feedback[0]),
             extraction_complete=False, prototype_handoff_qualified=False, release_qualified=False))
        status('filled_geometry_pass' if passed else 'filled_geometry_nonpass')
    except BaseException as e:
        status('failed', reason=repr(e)); raise


if __name__ == '__main__':
    main()
