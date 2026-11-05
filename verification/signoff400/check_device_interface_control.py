#!/usr/bin/env python3
"""Driven partial-diffusion native control for rectangular interface placement.

The synthetic notch is a source-geometry stress case, not a manufacturable
layout or a qualified physical transistor model.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from common import ROOT, save, sha
from resources import lease
from check_magic_origin_guard_v3 import matrix, devices


def creation_bounds(directory):
    rows, outside, pending = 0, [], []
    for line in (directory/'R_segments.log').open():
        f = shlex.split(line)
        if f[0] == 'SEG':
            pending.append(f)
        elif f[0] == 'GROUP':
            for s in pending:
                rows += 1
                box = list(map(int, s[8:12]))
                for endpoint in (0, 1):
                    point = list(map(int, s[4+2*endpoint:6+2*endpoint]))
                    if not (box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]):
                        outside.append(dict(group=f[1], conductor=f[2], branch=s[1], endpoint=endpoint,
                                            point=point, tile_box=box, raw_material_type=s[13]))
            pending = []
    if pending or not rows:
        raise ValueError('complete nonempty grouped creation stream required')
    return rows, outside


def run(baseline_build, candidate_build, template, output):
    baseline_build, candidate_build, template, out = (Path(p).resolve() for p in
        (baseline_build, candidate_build, template, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=1, memory_limit_GiB=8, automatic_identical_retry=False))
    try:
        with lease(1, 8, deadline):
            parent = json.loads((baseline_build/'assessment.json').read_text())
            raw = template.read_text()
            text = (raw[:raw.index('box values 2.125um')] +
                'box values 1.96um 0.51um 2.07um 1.11um\nerase ndiff\n' + raw[raw.index('extract style ngspice()'):])
            pins = {str(p): sha(p) for p in (baseline_build/'assessment.json', template, Path(__file__).resolve(),
                Path(__file__).with_name('check_magic_origin_guard_v3.py'), Path(__file__).with_name('common.py'),
                Path(__file__).with_name('resources.py'),
                ROOT/'build/timing400/release_001/capacitance_corner_controls_001/nand2_2.gds',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech')}
            records = {}
            for name in ('original', 'candidate'):
                if name == 'candidate':
                    status('waiting_for_isolated_device_interface_build')
                    while not (candidate_build/'assessment.json').exists():
                        if (candidate_build/'status.json').exists() and json.loads((candidate_build/'status.json').read_text())['state'] == 'failed':
                            raise RuntimeError('candidate native build failed')
                        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                            raise TimeoutError('whole native control deadline exhausted')
                        time.sleep(1)
                    candidate = json.loads((candidate_build/'assessment.json').read_text())
                    if not candidate['experimental_rectangular_device_interface_build_completed']:
                        raise ValueError('expected device-interface source variant')
                    pins[str(candidate_build/'assessment.json')] = sha(candidate_build/'assessment.json')
                    report = candidate
                else:
                    report = parent
                prefix = Path(report['prefix'])
                binary = prefix/'bin/magic'
                for p in (binary, prefix/'lib/magic/tcl/tclmagic.so'):
                    h = sha(p)
                    if h != report['artifacts'][str(p)]:
                        raise ValueError('native binary/library differs from exact build receipt')
                    pins[str(p)] = h
                target = out/name
                target.mkdir()
                task = target/'control.tcl'
                task.write_text(text)
                pins[str(task)] = sha(task)
                env = dict(os.environ, PDK_ROOT=str(ROOT/'build/timing450/pdk'),
                    OPENPLL_R_TILE_DOMAIN_TRACE='1', OPENPLL_R_RETAIN_MESH='1',
                    OPENPLL_R_NODE_TRACE_FILE=str(target/'R_provenance.log'),
                    OPENPLL_R_SEGMENT_TRACE_FILE=str(target/'R_segments.log'),
                    OPENPLL_R_BIND_TRACE_FILE=str(target/'R_bindings.log'))
                command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
                    ROOT/'build/apptainer/openpll-release-modern.sif', binary, '-dnull', '-noconsole', '-rcfile',
                    ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc', task]
                status('driven_partial_diffusion_native_running', tool=name)
                with (target/'native.log').open('x') as log:
                    subprocess.run(command, cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT, check=True,
                        timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
                if 'LABEL_BREAKPOINT_DRIVEN_CONTROL_COMPLETE' not in (target/'native.log').read_text():
                    raise ValueError('native case completion absent')
                records[name] = creation_bounds(target)
                if name == 'original' and not records[name][1]:
                    raise ValueError('partial diffusion control did not reproduce outside breakpoint')
            if records['candidate'][1]:
                raise ValueError('candidate has outside branch-creation coordinates')
            a, b = out/'original', out/'candidate'
            if matrix(a/'before.spice') != matrix(b/'before.spice') or devices(a/'LABEL_SPAN_DRIVEN.ext') != devices(b/'LABEL_SPAN_DRIVEN.ext'):
                raise ValueError('pre-R C or native device parameters changed')
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('device control input changed: '+p)
            result = dict(input_sha256=pins,
                artifacts={str(p): sha(p) for p in out.rglob('*') if p.is_file() and p.name != 'status.json'},
                original_creation_segments=records['original'][0], candidate_creation_segments=records['candidate'][0],
                original_outside_creation_endpoints=records['original'][1], candidate_outside_creation_endpoints=[],
                pre_R_C_and_native_devices_unchanged=True, partial_diffusion_native_control_passed=True,
                synthetic_geometry_stress_only=True, manufacturable_control_qualified=False,
                full_native_regression_passed=False, physical_RC_qualified=False, release_qualified=False,
                adopted=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            status('partial_diffusion_source_control_passed_full_qualification_pending')
            return result
    except BaseException as exc:
        status('failed', reason=repr(exc))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-build', 'candidate-build', 'template', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.baseline_build, a.candidate_build, a.template, a.output)))
