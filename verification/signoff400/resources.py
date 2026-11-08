"""Cross-process CPU/RAM leases with PID birth identity and host memory reserve."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time

from runtime_common import ROOT, save

GIB = 1024 ** 3


def identity(pid):
    try:
        # comm may contain spaces or parentheses; fields begin after its final ')'.
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except FileNotFoundError:
        return None


def available_memory():
    return next(int(row.split()[1]) * 1024 for row in Path('/proc/meminfo').read_text().splitlines()
                if row.startswith('MemAvailable:'))


@contextmanager
def lease(cpus, memory_gib, deadline, *, directory=None, cpu_limit=32,
          memory_limit_gib=200, reserve_gib=32):
    """All new flow jobs share this admission point, including nested tool threads."""
    if not 1 <= cpus <= cpu_limit or not 0 < memory_gib <= memory_limit_gib:
        raise ValueError('resource request exceeds host budget')
    directory = Path(directory or ROOT / 'build/signoff400/resources')
    directory.mkdir(parents=True, exist_ok=True)
    state, lockpath = directory / 'leases.json', directory / 'leases.lock'
    token = f'{os.getpid()}:{identity(os.getpid())}:{time.monotonic_ns()}'
    while True:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('whole-check deadline exhausted waiting for resources')
        with lockpath.open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            entries = json.loads(state.read_text()) if state.exists() else {}
            entries = {k: v for k, v in entries.items() if identity(v['pid']) == v['birth']}
            # Use the tightest policy of all live claimants.
            cpu_cap = min([cpu_limit] + [v['cpu_limit'] for v in entries.values()])
            mem_cap = min([memory_limit_gib] + [v['memory_limit_gib'] for v in entries.values()])
            admitted = (sum(v['cpus'] for v in entries.values()) + cpus <= cpu_cap
                        and sum(v['memory_gib'] for v in entries.values()) + memory_gib <= mem_cap
                        and available_memory() >= (memory_gib + reserve_gib) * GIB)
            if admitted:
                entries[token] = dict(pid=os.getpid(), birth=identity(os.getpid()), cpus=cpus,
                                      memory_gib=memory_gib, cpu_limit=cpu_limit,
                                      memory_limit_gib=memory_limit_gib)
            save(state, entries)
        if admitted:
            break
        time.sleep(min(1, max(.001, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    try:
        yield token
    finally:
        with lockpath.open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            entries = json.loads(state.read_text())
            entries.pop(token, None)
            save(state, entries)
