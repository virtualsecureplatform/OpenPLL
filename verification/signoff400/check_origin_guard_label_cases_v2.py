#!/usr/bin/env python3
"""Parallel native label-origin controls at three extraction RC rule corners.

Archives raw local-SSD cases. This is extractor regression, not 400 MHz PVT,
device-interface or full-layout model qualification.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
from common import ROOT, save, sha
from resources import lease
from check_magic_origin_guard_v3 import outside_origins, matrix, devices


def graph(directory):
    groups, current = {}, None
    for line in (directory/'R_provenance.log').open():
        f = shlex.split(line)
        if f[0] == 'BEGIN':
            groups[f[1]] = dict(label=f[2], nodes={}, edges={})
        elif f[0] == 'NODE':
            groups[f[1]]['nodes'][f[2]] = (f[3], *map(int, f[4:]))
        elif f[0] == 'BRANCH':
            current = (f[1], f[3])
        elif f[0] == 'EDGE':
            if current is None or current[0] != f[1]:
                raise ValueError('branch provenance sequence')
            g = groups[f[1]]
            row = (f[3], f[4], *f[5:])
            if current[1] in g['edges'] and g['edges'][current[1]] != row:
                raise ValueError('branch endpoint provenance differs')
            g['edges'][current[1]] = row
            current = None
    result = []
    for group in groups.values():
        nodes = group['nodes']
        if len(set(nodes.values())) != len(nodes):
            raise ValueError('ambiguous coordinate/name identity in unchanged-graph control')
        edges = Counter()
        for a, b, *values in group['edges'].values():
            ends = tuple(sorted((nodes[a], nodes[b])))
            edges[ends, tuple(values)] += 1
        result.append((group['label'], Counter(nodes.values()), edges))
    return result


def task(job):
    case, corner, original, candidate, template, scratch, deadline = job
    root = Path(scratch)/(corner+'_'+case)
    root.mkdir()
    text = template.replace('extract style ngspice()', 'extract style '+dict(
        nom='ngspice()', min='ngspice(lrlc)', max='ngspice(hrhc)')[corner])
    if case == 'contained_y':
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.94um 1.28um 5um 1.32um')
    elif case == 'boundary_y':
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.94um 1.33um 5um 2um')
    elif case == 'span_x':
        text = text.replace('box values 4.94um 1.33um 5um 6um', 'box values 5um 1.26um 9um 1.32um')
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.995um 1.27um 6um 1.31um')
        text = text.replace('box values 4.95um 5.5um 4.99um 5.8um', 'box values 8.5um 1.27um 8.8um 1.31um')
    records = {}
    for name, binary in [('original', original), ('candidate', candidate)]:
        target = root/name
        target.mkdir()
        script = target/'control.tcl'
        script.write_text(text)
        env = dict(os.environ, PDK_ROOT=str(ROOT/'build/timing450/pdk'),
            OPENPLL_R_TILE_DOMAIN_TRACE='1', OPENPLL_R_RETAIN_MESH='1',
            OPENPLL_R_NODE_TRACE_FILE=str(target/'R_provenance.log'),
            OPENPLL_R_SEGMENT_TRACE_FILE=str(target/'R_segments.log'),
            OPENPLL_R_BIND_TRACE_FILE=str(target/'R_bindings.log'))
        command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
            ROOT/'build/apptainer/openpll-release-modern.sif', binary, '-dnull', '-noconsole', '-rcfile',
            ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc', script]
        with (target/'native.log').open('x') as log:
            subprocess.run(command, cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        if 'LABEL_BREAKPOINT_DRIVEN_CONTROL_COMPLETE' not in (target/'native.log').read_text():
            raise ValueError('native completion marker absent')
        records[name] = outside_origins(target)
    old, labels = records['original']
    new, new_labels = records['candidate']
    expected = 2 if case in ('span_y', 'span_x') else 0
    if len(old) != expected or new:
        raise ValueError(f'{corner}/{case}: unexpected outside-origin counts {len(old)} -> {len(new)}')
    if {tuple(r['point']) for r in labels} != {tuple(r['point']) for r in new_labels} or not new_labels:
        raise ValueError('label drivepoint coordinates changed')
    a, b = root/'original', root/'candidate'
    if matrix(a/'before.spice') != matrix(b/'before.spice') or devices(a/'LABEL_SPAN_DRIVEN.ext') != devices(b/'LABEL_SPAN_DRIVEN.ext'):
        raise ValueError('pre-R capacitance or device difference')
    unchanged = case in ('contained_y', 'boundary_y')
    if unchanged and graph(a) != graph(b):
        raise ValueError('valid/boundary native R graph changed')
    result = dict(case=case, RC_rule_corner=corner, original_outside_origins=len(old), candidate_outside_origins=len(new),
         original_drivepoints_preserved=True, pre_R_C_and_devices_unchanged=True,
         unchanged_R_graph_checked=unchanged, physical_RC_qualified=False, release_qualified=False)
    save(root/'result.json', result)
    return root, result


def run(build, control, baseline, output):
    build, control, baseline, out = (Path(p).resolve() for p in (build, control, baseline, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline, scratch, pool = start+43200, None, None
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=6, memory_limit_GiB=8, automatic_identical_retry=False))
    try:
        with lease(6, 8, deadline):
            b, c = (json.loads((p/'assessment.json').read_text()) for p in (build, control))
            if not c['driven_targeted_native_case_passed'] or c['input_sha256'].get(str(build/'assessment.json')) != sha(build/'assessment.json'):
                raise ValueError('completed matching driven build/control required')
            original = ROOT/'build/timing400/magic_R_tile_domain_trace_623_001/bin/magic'
            candidate = Path(b['prefix'])/'bin/magic'
            paths = [build/'assessment.json', control/'assessment.json', baseline/'control.tcl', original, candidate,
                original.parents[1]/'lib/magic/tcl/tclmagic.so', candidate.parents[1]/'lib/magic/tcl/tclmagic.so',
                Path(__file__).resolve(), ROOT/'build/timing400/release_001/capacitance_corner_controls_001/nand2_2.gds',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc',
                *[Path(__file__).with_name(n) for n in ('common.py', 'resources.py', 'check_magic_origin_guard_v3.py')]]
            pins = {str(p): sha(p) for p in paths}
            for p, h in c['artifacts'].items():
                if sha(p) != h:
                    raise ValueError('driven native control artifact changed')
            scratch = Path(tempfile.mkdtemp(prefix='openpll-origin-cases-', dir='/tmp'))
            save(out/'input_manifest.json', dict(input_sha256=pins, retained_local_scratch=str(scratch)))
            template = (baseline/'control.tcl').read_text()
            jobs = [(case, corner, original, candidate, template, str(scratch), deadline)
                    for corner in ('min', 'nom', 'max') for case in ('span_y', 'contained_y', 'boundary_y', 'span_x')]
            status('parallel_native_origin_cases_running', native_runs=24, workers=6)
            pool = ProcessPoolExecutor(max_workers=6)
            futures = [pool.submit(task, job) for job in jobs]
            results, artifacts = [], {}
            for future in as_completed(futures, timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))):
                directory, result = future.result()
                archive = out/(directory.name+'.tar')
                with tarfile.open(archive, 'x') as stream:
                    stream.add(directory, arcname=directory.name)
                artifacts[str(archive)] = sha(archive)
                results.append(result)
                status('parallel_native_origin_cases_running', completed_pairs=len(results), total_pairs=len(jobs))
            pool.shutdown()
            pool = None
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('native case input changed: '+p)
            save(out/'cases.json', sorted(results, key=lambda r: (r['RC_rule_corner'], r['case'])))
            artifacts[str(out/'cases.json')] = sha(out/'cases.json')
            result = dict(input_sha256=pins, artifacts=artifacts, native_runs=24, case_pairs=len(results),
                native_R_graph_unchanged_case_pairs=sum(r['unchanged_R_graph_checked'] for r in results),
                original_outside_origins=sum(r['original_outside_origins'] for r in results),
                candidate_outside_origins=sum(r['candidate_outside_origins'] for r in results),
                label_corner_native_controls_passed=True, full_native_regression_passed=False,
                full_layout_outside_geometry_resolved=False, physical_RC_qualified=False, resistance_PVT_qualified=False,
                release_qualified=False, adopted=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            shutil.rmtree(scratch)
            status('label_corner_controls_complete_full_qualification_pending')
            return result
    except BaseException as exc:
        if pool is not None:
            for p in pool._processes.values():
                p.terminate()
            pool.shutdown(wait=True, cancel_futures=True)
        status('failed', reason=repr(exc), retained_scratch=str(scratch) if scratch else None)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'control', 'baseline', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.build, a.control, a.baseline, a.output)))
