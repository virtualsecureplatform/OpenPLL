#!/usr/bin/env python3
"""Enforce a wall-clock budget on this workspace's native Xyce checks.

Does not modify frozen runners or interpret a timeout as verification success.
Uses Linux process identity and pidfds so recycled PIDs cannot be signalled.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time
from datetime import datetime, timezone


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def process(pid, workspace, proc=Path('/proc')):
    """Return only a native Xyce process writing inside this workspace."""
    try:
        directory = proc / str(pid)
        argv = (directory / 'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        if argv[0] != '/opt/xyce/bin/Xyce' or '-o' not in argv:
            return None
        output = argv[argv.index('-o') + 1]
        path = Path(output)
        if path.is_relative_to('/work/OpenPLL'):
            # Verify the bind mount through the process's mount namespace.
            # Cwd may be in the PDK; alias text alone cannot identify a workspace.
            if not os.path.samefile(directory / 'root/work/OpenPLL', workspace):
                return None
            path = workspace / path.relative_to('/work/OpenPLL')
        path = path.resolve()
        if not path.is_relative_to(workspace / 'build'):
            return None
        stat = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        start_ticks = int(stat[19])
        return {'pid': int(pid), 'start_ticks': start_ticks, 'argv': argv,
                'output': str(path)}
    except (OSError, UnicodeError, ValueError, IndexError):
        return None


def elapsed(check):
    return float(Path('/proc/uptime').read_text().split()[0]) - check['start_ticks'] / os.sysconf('SC_CLK_TCK')


def send(check, sig, workspace):
    """Open the process handle, recheck its identity, then signal that handle."""
    try:
        fd = os.pidfd_open(check['pid'])
    except ProcessLookupError:
        return False
    try:
        current = process(check['pid'], workspace)
        if current != check:
            return False
        signal.pidfd_send_signal(fd, sig)
        return True
    except ProcessLookupError:
        return False
    finally:
        os.close(fd)


def partial_observation(check):
    wave = Path(check['output'] + '.prn')
    try:
        with wave.open('rb') as stream:
            stream.seek(max(0, wave.stat().st_size - 4096))
            rows = [s for s in stream.read().decode(errors='replace').splitlines()
                    if len(s.split()) >= 3 and s.split()[0].isdigit()]
        return {'waveform': str(wave), 'last_observed_row': rows[-1] if rows else None,
                'growing_waveform_hashed': False}
    except OSError:
        return {'waveform': str(wave), 'last_observed_row': None}


def watch(workspace, output, hours, grace_seconds):
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'watchdog.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        policy = {'started_utc': utc(), 'watchdog_pid': os.getpid(),
                  'boot_id': boot_id, 'workspace': str(workspace),
                  'budget_hours_per_native_check': hours,
                  'termination_grace_seconds': grace_seconds,
                  'includes_already_elapsed_runtime': True,
                  'timeout_is_pass': False, 'automatic_retry': False,
                  'existing_pinned_helpers_modified': False,
                  'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        save(output / 'policy.json', policy)
        print(json.dumps(policy), flush=True)
        pending = {}
        while True:
            live = []
            for entry in Path('/proc').iterdir():
                if entry.name.isdigit():
                    check = process(int(entry.name), workspace)
                    if check:
                        live.append(check)
            now = time.monotonic()
            for check in live:
                key = f"{boot_id}_{check['pid']}_{check['start_ticks']}"
                receipt = output / (key + '.json')
                if key in pending or elapsed(check) < hours * 3600:
                    continue
                # Write intent before signalling; retain every partial result.
                record = {'observed_utc': utc(), 'process': check,
                          'elapsed_seconds_at_timeout': elapsed(check),
                          'budget_hours': hours, 'outcome': 'TIMEOUT',
                          'verification_pass': False, 'release_qualified': False,
                          'scope': 'Execution budget exhausted; not a circuit failure or completed simulation.',
                          'partial_observation': partial_observation(check)}
                if receipt.exists():
                    record = json.loads(receipt.read_text())
                save(receipt, record)
                record['sigterm_sent'] = send(check, signal.SIGTERM, workspace)
                save(receipt, record)
                pending[key] = (check, record, now, receipt)
                print(json.dumps({'timeout': check['pid'], 'receipt': str(receipt)}), flush=True)
            for key, (check, record, when, receipt) in list(pending.items()):
                current = process(check['pid'], workspace)
                if current != check:
                    record['process_exit_observed_utc'] = utc()
                    record['partial_observation_after_exit'] = partial_observation(check)
                    save(receipt, record)
                    del pending[key]
                elif now - when >= grace_seconds and not record.get('sigkill_sent'):
                    record['sigkill_sent'] = send(check, signal.SIGKILL, workspace)
                    save(receipt, record)
            save(output / 'status.json', {'observed_utc': utc(), 'live_native_checks': len(live),
                 'termination_pending': len(pending), 'budget_hours': hours,
                 'timeout_receipts': len(list(output.glob(f'{boot_id}_*.json'))),
                 'release_qualified': False})
            time.sleep(5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hours', type=float, default=12)
    parser.add_argument('--grace-seconds', type=float, default=30)
    args = parser.parse_args()
    assert math.isfinite(args.hours) and 0 < args.hours <= 12
    assert math.isfinite(args.grace_seconds) and 0 < args.grace_seconds <= 30
    watch(args.workspace.resolve(), args.output.resolve(), args.hours, args.grace_seconds)
