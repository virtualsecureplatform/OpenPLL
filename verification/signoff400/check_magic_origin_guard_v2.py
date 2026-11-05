#!/usr/bin/env python3
"""Targeted driven native regression of an isolated origin-containment patch.

Checks one reproducer, not full native extraction or physical RC qualification.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
from common import ROOT, save, sha
from resources import lease


def outside_origins(directory):
    nodes, final, labels = {}, set(), []
    branch = None
    for line in (directory/'R_provenance.log').open():
        f = shlex.split(line)
        if f[0] == 'NODE':
            nodes[f[1], f[2]] = dict(name=f[3], point=list(map(int, f[4:6])), why=int(f[6]))
            if f[3] == 'LABEL_SPAN':
                labels.append(dict(group=f[1], point=list(map(int, f[4:6])), why=int(f[6])))
        elif f[0] == 'BRANCH':
            branch = (f[1], f[3])
        elif f[0] == 'EDGE':
            if branch is None or branch[0] != f[1]:
                raise ValueError('native branch/edge sequence mismatch')
            final.add(branch)
            branch = None
    pending, outside = [], []
    for line in (directory/'R_segments.log').open():
        f = shlex.split(line)
        if f[0] == 'SEG':
            pending.append(f)
        elif f[0] == 'GROUP':
            group = f[1]
            for s in pending:
                if (group, s[1]) not in final:
                    continue
                status = int(s[14])
                if bool(status & 512) == bool(status & 1024):
                    raise ValueError('one native wire axis required')
                axis = 0 if status & 512 else 1
                box = list(map(int, s[8:12]))
                for endpoint in (0, 1):
                    point = list(map(int, s[4+2*endpoint:6+2*endpoint]))
                    node = nodes[group, s[2+endpoint]]
                    if (node['why'] & 8) and not box[axis] <= point[axis] <= box[axis+2]:
                        outside.append(dict(group=group, label=f[2], node=node, point=point,
                                            tile_box=box, axis=axis, native_branch=s[1]))
            pending = []
    if pending:
        raise ValueError('unassigned trailing segment group')
    return outside, labels


NUMBER = re.compile(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(meg|[fpnumkg]?)$', re.I)
SCALE = {'': '1.0', 'f': '1e-15', 'p': '1e-12', 'n': '1e-9', 'u': '1e-6',
         'm': '0.001', 'k': '1000.0', 'meg': '1000000.0', 'g': '1000000000.0'}


def matrix(path):
    result = defaultdict(Decimal)
    for line in path.open():
        if line.startswith('C'):
            f = line.split()
            m = NUMBER.fullmatch(f[3])
            if m is None:
                raise ValueError('native capacitor value syntax')
            result[tuple(sorted(f[1:3]))] += Decimal(m[1])*Decimal(SCALE[m[2].lower()])
    return {k: v for k, v in result.items() if v}


def devices(path):
    return Counter(' '.join(line.split()) for line in path.open() if line.startswith('device '))


def run(build, baseline, output):
    build, baseline, out = (Path(p).resolve() for p in (build, baseline, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=1, memory_limit_GiB=8,
         automatic_identical_retry=False, existing_extraction_unchanged=True))
    try:
        with lease(1, 8, deadline):
            status('waiting_for_exact_experimental_build')
            while not (build/'assessment.json').exists():
                if (build/'status.json').exists() and json.loads((build/'status.json').read_text())['state'] == 'failed':
                    raise RuntimeError('experimental source build failed')
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('whole native control deadline exhausted')
                time.sleep(1)
            receipt = build/'assessment.json'
            b = json.loads(receipt.read_text())
            if not b['experimental_origin_guard_build_completed'] or b['adopted']:
                raise ValueError('expected unadopted experimental build')
            immutable = {**b['input_sha256'], **b['diagnostic_source_files'], **b['artifacts']}
            # The producer hashes status before its final transition. Validate
            # that single known mutable transition, and pin all immutable bytes.
            status_path = build/'status.json'
            expected = dict(state='building_experimental_origin_guard', stage='install', release_qualified=False)
            expected_hash = hashlib.sha256((json.dumps(expected, indent=2)+'\n').encode()).hexdigest()
            if str(status_path) in immutable:
                if immutable.pop(str(status_path)) != expected_hash:
                    raise ValueError('unexpected original mutable build status hash')
            elif not b.get('mutable_status_excluded_from_artifacts'):
                raise ValueError('build status artifact policy not established')
            if json.loads(status_path.read_text()) != dict(
                    state='experimental_build_complete_native_regression_required', release_qualified=False):
                raise ValueError('unexpected build status transition')
            for p, h in immutable.items():
                if sha(p) != h:
                    raise ValueError('experimental immutable build receipt mismatch: '+p)
            save(out/'immutable_build_validation.json', dict(immutable_artifacts_validated=True,
                 known_mutable_status_transition_explicitly_validated=True, input_sha256=immutable,
                 producer_receipt_sha256=sha(receipt), release_qualified=False))
            pins = {str(p): sha(p) for p in [receipt, Path(__file__).resolve(),
                *[p for p in baseline.iterdir() if p.is_file()],
                ROOT/'build/timing400/release_001/capacitance_corner_controls_001/nand2_2.gds',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech']}
            old, labels = outside_origins(baseline)
            if len(old) != 2 or any(r['node']['name'] != 'LABEL_SPAN' for r in old):
                raise ValueError('expected exact driven outside-label baseline')
            task = out/'control.tcl'
            shutil.copyfile(baseline/'control.tcl', task)
            pins[str(task)] = sha(task)
            binary = Path(b['prefix'])/'bin/magic'
            env = dict(os.environ, PDK_ROOT=str(ROOT/'build/timing450/pdk'),
                OPENPLL_R_TILE_DOMAIN_TRACE='1', OPENPLL_R_RETAIN_MESH='1',
                OPENPLL_R_NODE_TRACE_FILE=str(out/'R_provenance.log'),
                OPENPLL_R_SEGMENT_TRACE_FILE=str(out/'R_segments.log'),
                OPENPLL_R_BIND_TRACE_FILE=str(out/'R_bindings.log'))
            command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
                ROOT/'build/apptainer/openpll-release-modern.sif', binary, '-dnull', '-noconsole', '-rcfile',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc', task]
            status('driven_origin_guard_native_regression_running')
            with (out/'native.log').open('x') as log:
                subprocess.run(command, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, check=True,
                    timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            if 'LABEL_BREAKPOINT_DRIVEN_CONTROL_COMPLETE' not in (out/'native.log').read_text():
                raise ValueError('native control completion marker missing')
            new, new_labels = outside_origins(out)
            if new or not new_labels or any(r['point'] != [988, 265] for r in new_labels):
                raise ValueError('outside origin persists or original drivepoint changed')
            top = 'LABEL_SPAN_DRIVEN.ext'
            if matrix(baseline/'before.spice') != matrix(out/'before.spice') or devices(baseline/top) != devices(out/top):
                raise ValueError('pre-resistance C or device statements changed')
            for p, h in {**immutable, **pins}.items():
                if sha(p) != h:
                    raise ValueError('regression input changed: '+p)
            result = dict(input_sha256=pins, immutable_build_receipt=str(out/'immutable_build_validation.json'),
                artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'},
                baseline_outside_origin_branches=len(old), candidate_outside_origin_branches=len(new),
                original_label_drivepoint_preserved=True, pre_R_C_matrix_and_devices_unchanged=True,
                driven_targeted_native_case_passed=True, full_native_regression_passed=False,
                all_full_layout_outside_geometry_resolved=False, physical_RC_qualified=False,
                release_qualified=False, adopted=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            status('driven_origin_guard_case_passed_full_native_regression_required')
            return result
    except BaseException as exc:
        status('failed', reason=repr(exc))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'baseline', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.build, a.baseline, a.output)))
