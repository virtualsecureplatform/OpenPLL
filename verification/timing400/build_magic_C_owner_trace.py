#!/usr/bin/env python3
"""Build the isolated conductor-owner tracer; require native controls afterward."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    patch_path = base/'magic_C_owner_trace_patch_001/assessment.json'
    patch = json.loads(patch_path.read_text())
    assert patch['pair_kernel_owner_and_skipped_self_sidewall_diagnostics_added']
    assert all(digest(Path(p)) == h for p, h in patch['diagnostic_source_files'].items())
    source = root/'build/timing400/magic_C_owner_source_001'
    prefix = root/'build/timing400/magic_C_owner_trace_623_001'
    assert not prefix.exists()
    out = base/'magic_C_owner_trace_build_001'
    out.mkdir(exist_ok=False)
    tcl = Path('/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16')
    tk = Path('/nix/store/ay4rff85mnczgppg9rq6kshgymgis8yy-tk-8.6.16')
    tkincl = Path('/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev/include')
    compiler = Path('/nix/store/vr15iyyykg9zai6fpgvhcgyw7gckl78w-gcc-wrapper-14.3.0/bin/gcc')
    assert all(p.exists() for p in [tcl, tk, tkincl, compiler])
    configure = [str(source/'configure'), '--prefix='+str(prefix), '--with-tcl='+str(tcl/'lib'),
        '--with-tclincls='+str(tcl/'include'), '--with-tk='+str(tk/'lib'), '--with-tkincls='+str(tkincl),
        '--without-x', '--with-cairo=no', '--with-opengl=no', '--disable-readline', '--disable-threads', '--disable-modular']
    env = dict(os.environ, CC=str(compiler), CFLAGS='-O2 -g -std=gnu17',
        CPPFLAGS='-I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include')
    commands = [('configure', configure), ('bootstrap_header', ['/usr/bin/make', 'database/database.h']),
        ('make', ['/usr/bin/make', '-j4']), ('install', ['/usr/bin/make', 'install'])]
    inputs = [Path(__file__).resolve(), owner, patch_path, compiler, tcl/'lib/tclConfig.sh', tk/'lib/tkConfig.sh',
        tcl/'include/tcl.h', tkincl/'tk.h', *map(Path, patch['diagnostic_source_files'])]
    pins = {str(p): digest(p) for p in inputs}
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner), deadline_uptime=deadline, budget_restarted=False))
    save(out/'input_manifest.json', dict(input_sha256=pins, commands=commands,
        environment_overrides={k: env[k] for k in ['CC', 'CFLAGS', 'CPPFLAGS']}, isolated_prefix=str(prefix)))
    for name, command in commands:
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        with (out/(name+'.log')).open('x') as log:
            child = subprocess.Popen(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            save(out/'status.json', dict(state='building_isolated_owner_tracer', stage=name, child_pid=child.pid,
                runner_pid=os.getpid(), deadline_uptime=deadline))
            try:
                code = child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=10)
                save(out/'status.json', dict(state='timeout_inconclusive', stage=name))
                return
        if code:
            save(out/'status.json', dict(state='build_stage_nonpass', stage=name, exit_code=code))
            return
    assert all(digest(Path(p)) == h for p, h in pins.items())
    assert (prefix/'lib/magic/tcl/magicdnull').exists()
    artifacts = [p for p in prefix.rglob('*') if p.is_file()] + list(out.glob('*.log'))
    save(out/'assessment.json', dict(full_geometry_owner_trace_build_completed=True,
        installed_extractor_replaced=False, golden_Xyce_changed=False,
        native_equivalence_controls_passed=False, native_controls_required=True,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins, artifacts={str(p): digest(p) for p in artifacts}))
    save(out/'status.json', dict(state='build_completed_native_controls_required'))


if __name__ == '__main__':
    main()
