#!/usr/bin/env python3
"""Build an isolated rectangular device-interface candidate atop label containment.

Preserves the active extractor/source and its receipts. Not adopted without
native regression and complete physical/model qualification.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tarfile
import tempfile
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease

CAD_PYTHON = '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def inside(config):
    c = json.loads(Path(config).read_text())
    source, out, prefix = (Path(c[k]) for k in ('source', 'output', 'prefix'))
    tcl = Path('/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16')
    tk = Path('/nix/store/ay4rff85mnczgppg9rq6kshgymgis8yy-tk-8.6.16')
    tkincl = Path('/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev/include')
    env = dict(os.environ, CFLAGS='-O2 -g -std=gnu17',
        CC='/nix/store/vr15iyyykg9zai6fpgvhcgyw7gckl78w-gcc-wrapper-14.3.0/bin/gcc',
        CPPFLAGS='-I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include')
    commands = [('configure', [str(source/'configure'), '--prefix='+str(prefix),
        '--with-tcl='+str(tcl/'lib'), '--with-tclincls='+str(tcl/'include'),
        '--with-tk='+str(tk/'lib'), '--with-tkincls='+str(tkincl), '--without-x',
        '--with-cairo=no', '--with-opengl=no', '--disable-readline', '--disable-threads', '--disable-modular']),
        ('bootstrap_header', ['/usr/bin/make', 'database/database.h']),
        ('make', ['/usr/bin/make', '-j4']), ('install', ['/usr/bin/make', 'install'])]
    pins = {str(p): sha(p) for p in (Path(env['CC']), tcl/'lib/tclConfig.sh', tk/'lib/tkConfig.sh',
        tcl/'include/tcl.h', tkincl/'tk.h', Path('/usr/bin/make'))}
    save(out/'native_build_manifest.json', dict(commands=commands, input_sha256=pins,
         environment_overrides={k: env[k] for k in ('CC', 'CFLAGS', 'CPPFLAGS')}))
    for name, command in commands:
        save(out/'status.json', dict(state='building_experimental_origin_guard', stage=name, release_qualified=False))
        with (out/(name+'.log')).open('x') as log:
            subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=max(.01, c['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)))
    for p, h in pins.items():
        if sha(p) != h:
            raise ValueError('native build input changed: '+p)


def run(output):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    old = ROOT/'build/timing400/magic_R_tile_domain_source_001'
    source = Path(tempfile.mkdtemp(prefix='openpll-magic-origin-source-', dir='/tmp'))/'source'
    prefix = source.parent/'runtime'
    patch = ROOT/'build/signoff400/native_label_breakpoint_source_control_001/candidate_ResMain.patch'
    device_patch = ROOT/'build/signoff400/native_device_interface_patch_001/candidate_device_interface.patch'
    parent_build = ROOT/'build/signoff400/magic_origin_guard_build_002'
    parent_receipt = json.loads((parent_build/'assessment.json').read_text())
    commit = 'fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    save(out/'owner.json', dict(cpu_slots=4, memory_limit_GiB=8, wall_limit_s=43200,
         automatic_identical_retry=False, existing_source_and_extractor_unchanged=True))
    try:
        with lease(4, 8, deadline):
            if source.exists() or prefix.exists():
                raise FileExistsError('fresh source and isolated prefix required')
            if subprocess.check_output(['git', '-C', old, 'rev-parse', 'HEAD'], text=True).strip() != commit:
                raise ValueError('native source commit mismatch')
            names = [str(Path(n).relative_to(parent_receipt['source'])) for n in parent_receipt['diagnostic_source_files'] if str(Path(n).relative_to(parent_receipt['source'])) != 'resis/ResMain.c']
            pins = {str(p): sha(p) for p in (Path(__file__).resolve(), patch, device_patch, parent_build/'assessment.json',
                    *[old/n for n in names], old/'resis/ResMain.c')}
            baseline = out/'baseline.patch'
            baseline.write_bytes((parent_build/'baseline.patch').read_bytes())
            if sha(baseline) != parent_receipt['artifacts'][str(parent_build/'baseline.patch')]:
                raise ValueError('parent baseline patch changed')
            archive = parent_build/'base_source.tar'
            if parent_receipt['artifacts'][str(archive)] != sha(archive):
                raise ValueError('pinned Git source archive mismatch')
            shutil.copyfile(archive, out/'base_source.tar')
            source.mkdir(parents=True, exist_ok=False)
            with tarfile.open(out/'base_source.tar') as stream:
                stream.extractall(source, filter='data')
            subprocess.run(['git', '-C', source, 'apply', '--whitespace=nowarn', baseline], check=True)
            for name in names:
                if sha(source/name) != pins[str(old/name)]:
                    raise ValueError('baseline source clone mismatch: '+name)
            subprocess.run(['git', '-C', source, 'apply', '--check', patch], check=True)
            subprocess.run(['git', '-C', source, 'apply', patch], check=True)
            subprocess.run(['git', '-C', source, 'apply', '--check', device_patch], check=True)
            subprocess.run(['git', '-C', source, 'apply', device_patch], check=True)
            changed = names+['resis/ResMain.c']
            complete = []
            with tarfile.open(out/'base_source.tar') as original:
                for name in changed:
                    before = original.extractfile(name).read().decode()
                    after = (source/name).read_text()
                    complete.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
            (out/'complete_source.patch').write_text(''.join(complete))
            if set(changed) != set(names) | {'resis/ResMain.c'}:
                raise ValueError('unexpected source variant edits')
            source_pins = {str(source/n): sha(source/n) for n in changed}
            cfg = out/'build_config.json'
            save(cfg, dict(source=str(source), prefix=str(prefix), output=str(out), deadline_uptime=deadline))
            save(out/'input_manifest.json', dict(input_sha256=pins, diagnostic_source_files=source_pins,
                 upstream_commit=commit, installed_extractor_replaced=False))
            command = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
                ROOT/'build/apptainer/openpll-release-modern.sif', CAD_PYTHON, Path(__file__).resolve(), '--inside', cfg]
            execute(command, out/'driver.log', deadline, 8)
            binary = prefix/'lib/magic/tcl/magicdnull'
            if not binary.is_file():
                raise ValueError('isolated native binary missing')
            for p, h in {**pins, **source_pins}.items():
                if sha(p) != h:
                    raise ValueError('source changed during isolated build: '+p)
            with tarfile.open(out/'isolated_runtime.tar', 'x') as package:
                package.add(prefix, arcname='runtime')
            result = dict(input_sha256=pins, diagnostic_source_files=source_pins,
                artifacts={str(p): sha(p) for p in [*[p for p in out.iterdir() if p.is_file() and p.name != 'status.json'],
                    *[p for p in prefix.rglob('*') if p.is_file()]]}, source=str(source), prefix=str(prefix),
                experimental_origin_guard_build_completed=True, existing_source_unchanged=True,
                experimental_rectangular_device_interface_build_completed=True, local_runtime_retained=True,
                mutable_status_excluded_from_artifacts=True, local_source_retained=True,
                installed_extractor_replaced=False, native_regression_passed=False,
                physical_RC_qualified=False, release_qualified=False, adopted=False,
                elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            save(out/'status.json', dict(state='experimental_build_complete_native_regression_required', release_qualified=False))
            return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inside', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.inside:
        inside(a.inside)
    elif a.output:
        print(json.dumps(run(a.output)))
    else:
        p.error('--output or --inside required')
