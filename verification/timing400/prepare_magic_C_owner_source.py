#!/usr/bin/env python3
"""Create an isolated copy of the frozen C tracer for missing-owner diagnostics."""
import json
from pathlib import Path
import subprocess
import time

from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    old = root/'build/timing400/magic_C_kernel_source_001'
    source = root/'build/timing400/magic_C_owner_source_001'
    out = base/'magic_C_owner_source_preparation_001'
    assert not source.exists()
    out.mkdir(exist_ok=False)
    commit = subprocess.check_output(['git', '-C', str(old), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == 'fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    names = subprocess.check_output(['git', '-C', str(old), 'diff', '--name-only'], text=True).splitlines()
    assert 'extract/OpenPLLChargeTrace.h' in names
    pins = {str(old/n): digest(old/n) for n in names}
    patch = out/'frozen_C_kernel_baseline.patch'
    patch.write_bytes(subprocess.check_output(['git', '-C', str(old), 'diff', '--binary']))
    commands = [['git', '-C', str(old), 'worktree', 'add', '--quiet', '--detach', str(source), commit],
        ['git', '-C', str(source), 'apply', '--whitespace=nowarn', str(patch)]]
    for command in commands:
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        subprocess.run(command, check=True, timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    assert all(digest(old/n) == digest(source/n) == pins[str(old/n)] for n in names)
    result = dict(isolated_C_kernel_source_reproduced=True, diagnostic_files=len(names), source_commit=commit,
        original_frozen_source_unchanged=True, new_source=str(source), original_deadline_uptime=deadline,
        installed_extractor_replaced=False, native_analog_checks_added=0, runtime_model_eligible=False,
        release_qualified=False, adopted=False,
        input_sha256={str(Path(__file__).resolve()): digest(Path(__file__)), str(owner): digest(owner), **pins},
        artifacts={str(patch): digest(patch)}, reproduced_source_sha256={str(source/n): digest(source/n) for n in names})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print('Fresh isolated C tracer source is byte-identical to the frozen baseline; no native extraction started.')


if __name__ == '__main__':
    main()
