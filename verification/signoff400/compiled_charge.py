"""Build and invoke the compiled hot loop; retain the established JSON interfaces."""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

from common import ROOT, save, sha

SOURCE = ROOT / 'tools/charge_compiler'


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binary = output / 'charge_compiler'
    command = ['g++', '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic', '-pthread',
               '-fno-fast-math', '-ffp-contract=off', str(SOURCE / 'main.cpp'), '-o', str(binary)]
    with (output / 'build.log').open('x') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    save(output / 'build.json', dict(command=command,
         compiler_version=subprocess.check_output(['g++', '--version'], text=True),
         input_sha256={str(p): sha(p) for p in (SOURCE / 'main.cpp', SOURCE / 'json.hpp')},
         artifacts={str(binary.resolve()): sha(binary)}))
    return binary.resolve()


def execute(command, logpath, deadline, memory_gib=4):
    if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
        raise TimeoutError('compiled check exhausted whole-check budget')
    def limits():
        cap = int(memory_gib * 1024 ** 3)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    child = None
    try:
        with Path(logpath).open('x') as log:
            child = subprocess.Popen(list(map(str, command)), stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, preexec_fn=limits)
            from resources import identity
            save(Path(logpath).with_suffix('.process.json'),
                 dict(pid=child.pid, birth=identity(child.pid), process_group=child.pid))
            while child.poll() is None:
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('compiled check exhausted whole-check budget')
                try:
                    child.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    continue
            if child.returncode:
                raise RuntimeError(f'compiled worker failed ({child.returncode}): {logpath}')
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

def compile_shard(binary, trace, output, deadline, range_spec, metadata, memory_gib=4):
    started = time.monotonic()
    output = Path(output).resolve()
    config = output.with_suffix('.config.json')
    if output.exists() or config.exists():
        raise FileExistsError('fresh compiled shard required: ' + str(output))
    save(config, dict(trace=str(Path(trace).resolve()), output=str(output),
                     deadline_uptime=deadline, range_spec=range_spec,
                     metadata=str(Path(metadata).resolve())))
    execute([binary, 'compile', config], output.with_suffix('.log'), deadline, memory_gib)
    report = json.loads((output / 'native_summary.json').read_text())
    report['input_sha256'] = {str(p): sha(p) for p in
                             (Path(binary), SOURCE / 'main.cpp', SOURCE / 'json.hpp', config, Path(metadata))}
    report['artifacts'] = {str(output / name): sha(output / name) for name in
                          ('operators.jsonl', 'fields.json', 'collapsed_matrix_ledger.json',
                           'observed_plane_residues.json')}
    report['backend'] = 'c++20_streaming_signed_charge_v1'
    report['elapsed_s'] = time.monotonic() - started
    report['child_peak_rss_KiB'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    save(output / 'assessment.json', report)
    save(output / 'status.json', dict(state='completed', counts=report['counts'], deadline_uptime=deadline))
    return report
