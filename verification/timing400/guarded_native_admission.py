#!/usr/bin/env python3
"""Serialize external launches while dispatch is stopped until Xyce is visible.

Existing native children continue. All other external admission owners must
already have launched or use this guard. No pinned controller code is changed.
"""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from run_dco_qualification import ROOT, native_process, save


class AdmissionDeferred(Exception):
    pass


def eligible(status, native):
    if len(native) >= 4:
        raise AdmissionDeferred('four native slots occupied')
    if any(v.get('state') == 'waiting_for_native_slot' for v in status['stages'].values()):
        raise AdmissionDeferred('DCO reservation/preparation is in progress')
    engines = {v['engine_pid'] for v in status['stages'].values()
               if v.get('state') == 'running' and 'engine_pid' in v}
    if engines != {v['ppid'] for v in native if v['ppid'] in engines}:
        raise AdmissionDeferred('DCO engine is preparing or awaiting dispatch collection')
    return engines


def process_stat(pid):
    return (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()


def scan():
    result = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        item = native_process(int(p.name), ROOT)
        if item:
            try:
                item['ppid'] = int(process_stat(item['pid'])[1])
            except (OSError, ValueError):
                continue
            result.append(item)
    return result


def launch(command, env, log, controller_pid, receipt):
    """Return the single launched Popen, or defer before launching anything."""
    lock_path = ROOT/'build/timing400/guarded_native_admission.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AdmissionDeferred('another guarded external admission is in progress')
        p = Path('/proc')/str(controller_pid)
        argv = (p/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        assert str(ROOT/'verification/timing400/run_dco_qualification.py') in argv
        initial = process_stat(controller_pid)
        assert initial[0] not in ('T', 't', 'Z'), 'dispatch was already stopped'
        fd = os.pidfd_open(controller_pid)
        child, stopped, success = None, False, False
        guard = dict(dispatch_pid=controller_pid, dispatch_start_ticks=int(initial[19]),
                     native_children_paused=False, maximum_native_workers=4)
        started = time.monotonic()
        try:
            assert int(process_stat(controller_pid)[19]) == int(initial[19])
            signal.pidfd_send_signal(fd, signal.SIGSTOP)
            stopped = True
            until = time.monotonic()+2
            while any((t/'stat').read_text().rsplit(')', 1)[1].split()[0] not in ('T', 't')
                      for t in (p/'task').iterdir()):
                assert time.monotonic() < until, 'dispatch stop did not complete'
                time.sleep(.01)
            status = json.loads((ROOT/'build/timing400/release_001/dco/status.json').read_text())
            before = scan()
            engines = eligible(status, before)
            guard.update(native_before=before, running_dco_engines=sorted(engines))
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            until = time.monotonic()+2
            while True:
                after = scan()
                assert len(after) <= 4, 'workspace native capacity exceeded'
                visible = any(n['pid'] == child.pid for n in after)
                if visible or child.poll() is not None:
                    break
                assert time.monotonic() < until, 'new native process did not become visible'
                time.sleep(.01)
            guard.update(native_pid=child.pid, native_after=after,
                         native_visible_before_dispatch_resume=visible,
                         terminal_before_dispatch_resume=child.poll() is not None)
            success = True
        finally:
            if not success and child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if stopped:
                signal.pidfd_send_signal(fd, signal.SIGCONT)
            os.close(fd)
            guard.update(dispatch_resumed=stopped,
                         dispatch_stop_elapsed_s=time.monotonic()-started)
        try:
            save(receipt, guard)
        except BaseException:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            raise
        return child
