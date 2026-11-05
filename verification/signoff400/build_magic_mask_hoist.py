#!/usr/bin/env python3
"""Local isolated build of the invariant-mask performance-only source change."""
import argparse
import difflib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease
from build_magic_device_interface import inside, CAD_PYTHON


def run(parent, patch, control, output):
    parent, patch, control, out = (Path(p).resolve() for p in (parent, patch, control, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-mask-hoist-', dir='/tmp'))
    source, prefix = scratch/'source', scratch/'runtime'
    save(out/'owner.json', dict(cpu_slots=4, memory_limit_GiB=8, wall_limit_s=43200,
        automatic_identical_retry=False, existing_extractors_unchanged=True, local_scratch_retained=str(scratch)))
    try:
        with lease(4, 8, deadline):
            b, c = (json.loads((p/'assessment.json').read_text()) for p in (parent, control))
            if not b['experimental_rectangular_device_interface_build_completed'] or c['native_mask_comparisons'] != 600 or not c['missing_mask_copy_mutants_detected']:
                raise ValueError('completed exact parent and mask controls required')
            paths = [parent/'assessment.json', control/'assessment.json', patch, Path(__file__).resolve(),
                Path(__file__).with_name('build_magic_device_interface.py'),
                *[Path(__file__).with_name(n) for n in ('common.py', 'compiled_charge.py', 'resources.py')]]
            pins = {str(p): sha(p) for p in paths}
            for p, h in {**b['diagnostic_source_files'], **c['input_sha256'], **c['artifacts']}.items():
                if sha(p) != h:
                    raise ValueError('parent/control source changed: '+p)
            for name in ('base_source.tar', 'complete_source.patch'):
                p = parent/name
                if sha(p) != b['artifacts'][str(p)]:
                    raise ValueError('parent source archive/patch changed')
                shutil.copyfile(p, out/name)
                pins[str(p)] = sha(p)
            with tarfile.open(out/'base_source.tar') as stream:
                source.mkdir()
                stream.extractall(source, filter='data')
            subprocess.run(['git', '-C', source, 'apply', '--check', out/'complete_source.patch'], check=True)
            subprocess.run(['git', '-C', source, 'apply', out/'complete_source.patch'], check=True)
            names = [str(Path(p).relative_to(b['source'])) for p in b['diagnostic_source_files']]
            for name in names:
                if sha(source/name) != b['diagnostic_source_files'][str(Path(b['source'])/name)]:
                    raise ValueError('exact parent source reconstruction mismatch: '+name)
            subprocess.run(['git', '-C', source, 'apply', '--check', patch], check=True)
            subprocess.run(['git', '-C', source, 'apply', patch], check=True)
            source_pins = {str(source/name): sha(source/name) for name in names}
            complete = []
            with tarfile.open(out/'base_source.tar') as base:
                for name in names:
                    complete.extend(difflib.unified_diff(base.extractfile(name).read().decode().splitlines(True),
                        (source/name).read_text().splitlines(True), fromfile='a/'+name, tofile='b/'+name))
            (out/'complete_source.patch').write_text(''.join(complete))
            cfg = out/'build_config.json'
            save(cfg, dict(source=str(source), prefix=str(prefix), output=str(out), deadline_uptime=deadline))
            save(out/'input_manifest.json', dict(input_sha256=pins, diagnostic_source_files=source_pins,
                geometry_and_resistor_arithmetic_changed=False))
            command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
                ROOT/'build/apptainer/openpll-release-modern.sif', CAD_PYTHON, Path(__file__).resolve(), '--inside', cfg]
            execute(command, out/'driver.log', deadline, 8)
            with tarfile.open(out/'isolated_runtime.tar', 'x') as stream:
                stream.add(prefix, arcname='runtime')
            for p, h in {**pins, **source_pins}.items():
                if sha(p) != h:
                    raise ValueError('mask build input changed: '+p)
            result = dict(input_sha256=pins, diagnostic_source_files=source_pins, source=str(source), prefix=str(prefix),
                artifacts={str(p): sha(p) for p in [*[p for p in out.iterdir() if p.is_file() and p.name != 'status.json'],
                    *[p for p in prefix.rglob('*') if p.is_file()]]},
                experimental_origin_guard_build_completed=True, experimental_rectangular_device_interface_build_completed=True,
                experimental_mask_hoist_build_completed=True, geometry_and_resistor_arithmetic_changed=False,
                mutable_status_excluded_from_artifacts=True, existing_extractors_unchanged=True,
                native_regression_passed=False, physical_RC_qualified=False, release_qualified=False,
                adopted=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            save(out/'status.json', dict(state='mask_hoist_build_complete_native_regression_required', release_qualified=False))
            return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), retained_scratch=str(scratch), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inside', type=Path)
    for name in ('parent', 'patch', 'control', 'output'):
        p.add_argument('--'+name, type=Path)
    a = p.parse_args()
    if a.inside:
        inside(a.inside)
    elif all((a.parent, a.patch, a.control, a.output)):
        print(json.dumps(run(a.parent, a.patch, a.control, a.output)))
    else:
        p.error('all parent/patch/control/output arguments required')
