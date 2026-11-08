#!/usr/bin/env python3
"""Run an already Xyce-compatible deck with UMFPACK and bounded MPI resources.

This launcher preserves the deck and its output directives. It records native
process identity and timing; waveform qualification remains a separate check.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import identity, lease


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--deck', required=True, type=Path)
    parser.add_argument('--log', required=True, type=Path)
    parser.add_argument('--ranks', default=4, type=int)
    parser.add_argument('--cpus', help='CPU IDs; defaults to 0..ranks-1')
    parser.add_argument('--memory-gib', default=48, type=float)
    parser.add_argument('--wall-limit-s', default=7200, type=int)
    parser.add_argument('--experimental-checked-reuse', action='store_true',
                        help='Select the opt-in, not yet full-PLL-qualified reuse backend')
    parser.add_argument('--pin-ranks', action='store_true',
                        help='Pin each single-host OpenMPI rank to its selected CPU')
    args = parser.parse_args()
    cpus = set(range(args.ranks)) if args.cpus is None else {int(v) for v in args.cpus.split(',')}
    if not 1 <= args.ranks <= 32 or len(cpus) != args.ranks or not cpus <= set(range(32)):
        parser.error('one CPU per MPI rank, within CPU IDs 0..31, is required')
    if not 0 < args.memory_gib <= 200 or args.wall_limit_s <= 0:
        parser.error('positive time and memory budgets within the host policy required')
    binary, deck, log = args.binary.resolve(), args.deck.resolve(), args.log.resolve()
    if not binary.is_file() or not deck.is_file():
        parser.error('binary and deck must exist')
    manifest, status = log.with_suffix('.manifest.json'), log.with_suffix('.status.json')
    if any(p.exists() for p in (log, manifest, status, log.with_suffix('.process.json'))):
        parser.error('fresh log and metadata paths required')
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = started + args.wall_limit_s
    inputs = [binary, deck]
    rank_helper = Path(__file__).with_name('rank_exec.py')
    if args.pin_ranks:
        inputs.append(rank_helper)
    pins = {str(p): digest(p) for p in inputs}
    command = ['/usr/bin/mpirun', '--bind-to', 'none', '-np', str(args.ranks),
               str(binary), '-a', '-linsolv', 'umfpack_reuse' if args.experimental_checked_reuse else 'umfpack', str(deck)]
    if args.pin_ranks:
        command[5:5] = [sys.executable, str(rank_helper), '--cpus', ','.join(map(str, sorted(cpus))), '--']
    manifest.write_text(json.dumps(dict(command=command, input_sha256=pins,
        pinned_inputs_scope='top-level deck, binary and optional rank helper; transitive models are not inventoried',
        experimental_checked_reuse=args.experimental_checked_reuse,
        ranks_pinned_to_individual_CPUs=args.pin_ranks,
        CPUs=sorted(cpus), memory_GiB=args.memory_gib, native_wall_cap_s=args.wall_limit_s,
        owner_pid=os.getpid(), owner_birth=identity(os.getpid()),
        deadline_uptime=deadline, waveform_validation_performed=False, release_ready=False), indent=2) + '\n')

    def save(state, **extra):
        status.write_text(json.dumps(dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
            release_ready=False, **extra), indent=2) + '\n')

    try:
        os.sched_setaffinity(0, cpus)
        os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
        save('waiting_for_resource_lease')
        with lease(args.ranks, args.memory_gib, deadline):
            save('native_running')
            execute(command, log, deadline, args.memory_gib)
        for name, expected in pins.items():
            if digest(Path(name)) != expected:
                raise RuntimeError('Pinned input changed: ' + name)
        save('native_exit_success', waveform_validation_performed=False)
        print(status)
    except BaseException as error:
        save('stopped', reason=repr(error))
        raise


if __name__ == '__main__':
    main()
