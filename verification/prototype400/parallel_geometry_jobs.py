"""Run independent native geometry jobs with shared admission and cancellation."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from pathlib import Path
import os
import signal
import subprocess
import sys
import threading
import time

from common import ROOT, save, verify
sys.path.append(str(ROOT / 'verification/signoff400'))
from resources import identity, lease


def run_jobs(jobs, output, pins, deadline, workers=6, update=lambda **kw: None):
    """Density may return nonzero as measured evidence; other failures stop peers."""
    output = Path(output)
    active, results = {}, {}
    lock = threading.Lock()
    stopped = threading.Event()

    def stop():
        with lock:
            stopped.set()
            for child in active.values():
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def run(job):
        label = job['label']
        cpus, memory = job.get('cpus', 1), job.get('memory_gib', 8)
        with lease(cpus, memory, deadline):
            if stopped.is_set():
                raise RuntimeError('peer geometry job failed')
            verify(pins)
            with ExitStack() as stack:
                log = stack.enter_context((output / (label + '.log')).open('x'))
                stdin = stack.enter_context(Path(job['stdin']).open()) if job.get('stdin') else None
                command = ['/usr/bin/prlimit', '--as=' + str(memory * 1024**3), '--']
                command += list(map(str, job['command']))
                child = None
                try:
                    with lock:
                        if stopped.is_set():
                            raise RuntimeError('peer geometry job failed before launch')
                        started = time.clock_gettime(time.CLOCK_BOOTTIME)
                        child = subprocess.Popen(command, stdin=stdin, stdout=log,
                            stderr=subprocess.STDOUT, cwd=job.get('cwd', output),
                            env=job.get('env'), start_new_session=True)
                        active[label] = child
                        save(output / (label + '.process.json'), dict(pid=child.pid,
                            birth=identity(child.pid), process_group=child.pid, command=command,
                            cpu_slots=cpus, memory_limit_gib=memory, started_uptime=started, deadline_uptime=deadline))
                        update(active_jobs={name: process.pid for name, process in active.items()},
                               completed_jobs=len(results), total_jobs=len(jobs))
                    while True:
                        if stopped.is_set():
                            raise RuntimeError('peer geometry job failed while native process active')
                        remaining = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
                        if remaining <= 0:
                            raise TimeoutError('whole geometry deadline exhausted')
                        try:
                            code = child.wait(timeout=min(.25, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            pass
                    finished=time.clock_gettime(time.CLOCK_BOOTTIME)
                    save(output / (label + '.completion.json'), dict(native_exit=code,
                        started_uptime=started, finished_uptime=finished, elapsed_s=finished-started))
                    verify(pins)
                    if code and not job.get('allow_nonzero', False):
                        raise RuntimeError(f'{label} native exit {code}')
                    return label, code
                except BaseException:
                    stop()
                    raise
                finally:
                    if child is not None and child.poll() is None:
                        try:
                            os.killpg(child.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()
                    with lock:
                        active.pop(label, None)

    if len({job['label'] for job in jobs}) != len(jobs):
        raise ValueError('duplicate native geometry job labels')
    verify(pins)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, job) for job in jobs]
        try:
            for future in as_completed(futures):
                label, code = future.result()
                with lock:
                    results[label] = code
                    update(active_jobs={name: process.pid for name, process in active.items()},
                           completed_jobs=len(results), total_jobs=len(jobs))
        except BaseException:
            stop()
            for future in futures:
                future.cancel()
            raise
    verify(pins)
    return results
