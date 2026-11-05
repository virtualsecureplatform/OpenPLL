#!/usr/bin/env python3
"""Bounded read-only cache assistance for a birth-identified native trace reader.

Never writes trace files, changes the target FD, signals the reader, supplies a
digest or qualifies a receipt. Stops when that exact reader terminates.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from common import save, sha
from resources import identity, lease


def stamp(p):
    s = p.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def run(native, pid, output):
    native, out = Path(native).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    birth = identity(pid)
    if birth is None:
        raise ValueError('reader is not live')
    owner = json.loads((native/'owner.json').read_text())
    if owner['pid'] != pid or not (native/'trace/node_ids.json').exists():
        raise ValueError('expected exact completed-index trace owner')
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(owner['budget_started_utc'])).total_seconds()
    deadline = start+owner['wall_limit_s']-max(0, elapsed)
    files = {p.resolve(): stamp(p) for p in (native/'trace').iterdir() if p.is_file()}
    block, window = 8*1024**2, 512*1024**2
    read_bytes, batches, last_report = 0, 0, 0.
    ends, handles = {}, {}
    save(out/'owner.json', dict(target_pid=pid, target_birth=birth, original_owner=str(native/'owner.json'),
         original_deadline_preserved=True, cpu_slots=8, memory_lease_GiB=2,
         readers=8, bytes_per_read=block, maximum_ahead_bytes=window,
         target_descriptors_changed=False, automatic_identical_retry=False))
    save(out/'input_manifest.json', dict(trace_file_identity_snapshots={str(p): s for p, s in files.items()},
         input_sha256={str(Path(__file__).resolve()): sha(Path(__file__).resolve()),
                       str(native/'owner.json'): sha(native/'owner.json')}))
    def read_part(task):
        fd, offset, length = task
        total = 0
        while total < length:
            data = os.pread(fd, length-total, offset+total)
            if not data:
                raise ValueError('immutable trace file truncated')
            total += len(data)
        return total
    try:
        with lease(8, 2, deadline), ThreadPoolExecutor(max_workers=8) as pool:
            while identity(pid) == birth:
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('original native deadline exhausted')
                active = None
                # Observe paths and cursors through proc; open independent handles.
                for link in Path(f'/proc/{pid}/fd').iterdir():
                    try:
                        path = link.resolve(strict=True)
                        if path not in files or files[path][2] < 64*1024**2:
                            continue
                        pos = next(int(s.split()[1]) for s in Path(f'/proc/{pid}/fdinfo/{link.name}').read_text().splitlines() if s.startswith('pos:'))
                        active = path, pos
                        break
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                if active:
                    path, pos = active
                    if stamp(path) != files[path]:
                        raise ValueError('trace file changed during cache assistance: '+str(path))
                    if path not in handles:
                        handles[path] = os.open(path, os.O_RDONLY)
                    offset = max(pos//block*block, ends.get(path, 0))
                    limit = min(files[path][2], pos+window)
                    tasks = []
                    while offset < limit and len(tasks) < 8:
                        length = min(block, limit-offset)
                        tasks.append((handles[path], offset, length))
                        offset += length
                    if tasks:
                        read_bytes += sum(pool.map(read_part, tasks))
                        batches += 1
                        ends[path] = offset
                    else:
                        time.sleep(.1)
                else:
                    time.sleep(.1)
                now = time.clock_gettime(time.CLOCK_BOOTTIME)
                if now-last_report >= 10:
                    save(out/'status.json', dict(state='read_only_cache_assistance_live',
                         target_pid=pid, target_birth=birth, bytes_read=read_bytes, batches=batches,
                         reader_file=str(active[0]) if active else None,
                         observed_reader_offset=active[1] if active else None,
                         elapsed_s=now-start, release_qualified=False))
                    last_report = now
        save(out/'assessment.json', dict(stopped_on_original_reader_termination=True,
             cache_read_bytes=read_bytes, batches=batches, original_deadline_preserved=True,
             target_descriptors_changed=False, trace_files_written=False, checksums_supplied=False,
             physical_RC_qualified=False, release_qualified=False,
             elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start))
        save(out/'status.json', dict(state='original_reader_terminal_cache_assistance_stopped', release_qualified=False))
    except BaseException as exc:
        save(out/'status.json', dict(state='cache_assistance_failed_reader_unchanged', reason=repr(exc), release_qualified=False))
        raise
    finally:
        for fd in handles.values():
            os.close(fd)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', required=True, type=Path)
    p.add_argument('--pid', required=True, type=int)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    run(a.native, a.pid, a.output)
