#!/usr/bin/env python3
"""Exact native R/C/device comparison for the mask-only performance change."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT, save, sha
from resources import lease
from check_origin_guard_label_cases_v2 import graph
from check_magic_origin_guard_v3 import matrix, devices
from check_device_interface_control import creation_bounds


def run(build, reference_control, output):
    build, reference_control, out = (Path(p).resolve() for p in (build, reference_control, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=1, memory_limit_GiB=8,
                               automatic_identical_retry=False))
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    try:
        with lease(1, 8, deadline):
            status('waiting_for_completed_mask_hoist_build')
            while not (build/'assessment.json').exists():
                if (build/'status.json').exists() and json.loads((build/'status.json').read_text())['state'] == 'failed':
                    raise RuntimeError('mask build failed')
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('native mask control deadline')
                time.sleep(1)
            b, c = (json.loads((p/'assessment.json').read_text()) for p in (build, reference_control))
            if not b['experimental_mask_hoist_build_completed'] or not c['partial_diffusion_native_control_passed']:
                raise ValueError('matching mask build and completed interface reference required')
            for table in (b['input_sha256'], b['diagnostic_source_files'], c['input_sha256'], c['artifacts']):
                for p, h in table.items():
                    if sha(p) != h:
                        raise ValueError('native performance reference changed: '+p)
            prefix = Path(b['prefix'])
            binary = prefix/'bin/magic'
            library = prefix/'lib/magic/tcl/tclmagic.so'
            for p in (binary, library):
                if sha(p) != b['artifacts'][str(p)]:
                    raise ValueError('mask binary differs from completed build')
            reference = reference_control/'candidate'
            task = out/'control.tcl'
            shutil.copyfile(reference/'control.tcl', task)
            paths = [build/'assessment.json', reference_control/'assessment.json', task, binary, library,
                Path(__file__).resolve(), *[Path(__file__).with_name(n) for n in
                ('common.py', 'resources.py', 'check_origin_guard_label_cases_v2.py',
                 'check_magic_origin_guard_v3.py', 'check_device_interface_control.py')]]
            pins = {str(p): sha(p) for p in paths}
            env = dict(os.environ, PDK_ROOT=str(ROOT/'build/timing450/pdk'), OPENPLL_R_TILE_DOMAIN_TRACE='1',
                OPENPLL_R_RETAIN_MESH='1', OPENPLL_R_NODE_TRACE_FILE=str(out/'R_provenance.log'),
                OPENPLL_R_SEGMENT_TRACE_FILE=str(out/'R_segments.log'), OPENPLL_R_BIND_TRACE_FILE=str(out/'R_bindings.log'))
            command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
                ROOT/'build/apptainer/openpll-release-modern.sif', binary, '-dnull', '-noconsole', '-rcfile',
                ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.magicrc', task]
            status('native_mask_hoist_equivalence_running')
            with (out/'native.log').open('x') as log:
                subprocess.run(command, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, check=True,
                    timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            if 'LABEL_BREAKPOINT_DRIVEN_CONTROL_COMPLETE' not in (out/'native.log').read_text():
                raise ValueError('native completion marker absent')
            if graph(reference) != graph(out):
                raise ValueError('native R snapshot nodes/edges changed')
            if matrix(reference/'before.spice') != matrix(out/'before.spice') or devices(reference/'LABEL_SPAN_DRIVEN.ext') != devices(out/'LABEL_SPAN_DRIVEN.ext'):
                raise ValueError('native C/device statements changed')
            if creation_bounds(reference)[0] != creation_bounds(out)[0] or creation_bounds(out)[1]:
                raise ValueError('creation geometry/count changed')
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('mask native input changed: '+p)
            result = dict(input_sha256=pins,
                artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'},
                native_R_snapshot_graphs_equal=True, native_C_and_device_statements_equal=True,
                creation_segments_preserved=creation_bounds(out)[0], new_outside_creation_endpoints=0,
                targeted_native_mask_equivalence_passed=True, full_layout_numerical_equivalence_passed=False,
                native_speedup_measured=False, physical_RC_qualified=False, release_qualified=False, adopted=False,
                elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            status('targeted_native_mask_equivalence_passed_full_layout_check_pending')
            return result
    except BaseException as exc:
        status('failed', reason=repr(exc))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'reference-control', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.build, a.reference_control, a.output)))
