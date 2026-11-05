#!/usr/bin/env python3
"""Cross-simulator observation of the retained nominal FS125 NAND outlier.

Briefly stops only the dispatch process, never its native children, to reserve
one of four slots. Always resumes dispatch and bounds this small probe at60s.
No original waveform, model, solver choice, timing envelope or gate is adopted.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from run_dco_qualification import ROOT, native_process, sha, save
from characterize_nominal_hs_propagation import propagation


def stat(pid):
    return (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()


def natives():
    found = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        item = native_process(int(proc.name), ROOT)
        if item:
            item['ppid'] = int(stat(item['pid'])[1])
            found.append(item)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controller-pid', required=True, type=int)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    parent = ROOT/'build/timing450/interface_characterization/nominal_hs_propagation_001'
    source_path = parent/'assessment.json'
    source = json.loads(source_path.read_text())
    name = 'nand2_2_fs_1.8V_125C_200ps_5fF'
    reference = source['records'][name]
    assert reference['pass'] and reference['pvt'] == dict(corner='fs', supply_v=1.8, temperature_c=125)
    pins = {**source['sha256'], **reference['sha256']}
    original = parent/name/'cell.cir'
    ngspice = ROOT/'build/tools/ngspice47/install/bin/ngspice'
    for p in (source_path, original, ngspice, Path(__file__).resolve(),
              ROOT/'verification/timing450/characterize_nominal_hs_propagation.py'):
        pins[str(p)] = sha(p)
    for p, digest in pins.items():
        assert sha(p) == digest, p
    text = original.read_text()
    assert text.count('.options device temp=125') == 1
    assert text.count('.options timeint reltol=1e-5 abstol=1e-10') == 1
    text = text.replace('.options device temp=125', '.temp 125')
    text = text.replace('.options timeint reltol=1e-5 abstol=1e-10',
                        '.options reltol=1e-5 abstol=1e-10\n.option scale=1u')
    assert text.count('.print tran v(IN) v(OUT)') == 1 and text.rstrip().endswith('.end')
    text = text.replace('.print tran v(IN) v(OUT)', '')
    text = text.rstrip()[:-4]+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=17
run
wrdata {out}/waveform.dat v(IN) v(OUT)
quit
.endc
.end
'''
    out.mkdir(parents=True, exist_ok=False)
    deck = out/'cell.cir'
    deck.write_text(text)
    pins[str(deck)] = sha(deck)
    pid = args.controller_pid
    argv = (Path('/proc')/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    assert str(ROOT/'verification/timing400/run_dco_qualification.py') in argv
    before = stat(pid)
    assert before[0] not in ('T', 't', 'Z')
    status = json.loads((ROOT/'build/timing400/release_001/dco/status.json').read_text())
    active = {v['engine_pid'] for v in status['stages'].values() if v.get('state') == 'running' and 'engine_pid' in v}
    assert len(active) == 2 and not any(v.get('state') == 'waiting_for_native_slot' for v in status['stages'].values())
    initial_native = natives()
    assert len(initial_native) <= 3 and active <= {n['ppid'] for n in initial_native}
    guard = dict(observed_utc=datetime.now(timezone.utc).isoformat(), dispatch_pid=pid,
                 dispatch_start_ticks=int(before[19]), native_before=initial_native,
                 native_children_paused=False, reference_timeout_s=60,
                 release_qualified=False, automatic_identical_retry=False)
    fd = os.pidfd_open(pid)
    child = None
    paused = False
    started = time.monotonic()
    try:
        assert int(stat(pid)[19]) == int(before[19])
        signal.pidfd_send_signal(fd, signal.SIGSTOP)
        paused = True
        stop_deadline = time.monotonic()+2
        while any((p/'stat').read_text().rsplit(')', 1)[1].split()[0] not in ('T', 't')
                  for p in (Path('/proc')/str(pid)/'task').iterdir()):
            assert time.monotonic() < stop_deadline
            time.sleep(.01)
        current = natives()
        assert len(current) <= 3 and active <= {n['ppid'] for n in current}
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
        with (out/'run.log').open('x') as log:
            child = subprocess.Popen([str(ngspice), '-b', str(deck)], stdout=log,
                                     stderr=subprocess.STDOUT, env=env, start_new_session=True)
            guard['reference_native_pid'] = child.pid
            guard['maximum_combined_native_count_observed'] = len(current)+1
            deadline = time.monotonic()+60
            while child.poll() is None:
                count = len(natives())+1
                guard['maximum_combined_native_count_observed'] = max(count, guard['maximum_combined_native_count_observed'])
                assert count <= 4, 'workspace native capacity exceeded'
                if time.monotonic() >= deadline:
                    raise TimeoutError('small cross-simulator reference budget reached')
                time.sleep(.1)
            guard['reference_exit_code'] = child.returncode
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if paused:
            signal.pidfd_send_signal(fd, signal.SIGCONT)
        os.close(fd)
        guard['dispatch_resumed'] = paused and int(stat(pid)[19]) == int(before[19])
        guard['dispatch_pause_elapsed_s'] = time.monotonic()-started
        save(out/'slot_guard.json', guard)
    assert guard['reference_exit_code'] == 0, (out/'run.log').read_text()[-3000:]
    rows = []
    with (out/'waveform.dat').open() as stream:
        assert [c.lower() for c in stream.readline().split()] == ['time', 'v(in)', 'v(out)']
        for i, line in enumerate(stream):
            values = list(map(float, line.split()))
            assert len(values) == 3 and all(map(math.isfinite, values))
            rows.append([i, *values])
    assert rows[0][1] == 0 and rows[-1][1] >= 5e-9-1e-15
    assert all(a[1] < b[1] for a, b in zip(rows, rows[1:]))
    measured = propagation(rows, inverted=True)
    for p, digest in pins.items():
        assert sha(p) == digest, p
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()},
        source_case=name, pvt=reference['pvt'], ngspice_delays_ns=measured,
        xyce_delays_ns={k: reference[k] for k in measured},
        ngspice_minus_xyce_ps={k: (measured[k]-reference[k])*1000 for k in measured},
        source_geometry_and_RC_unchanged=True, explicit_geometry_scale='1u',
        model_version_or_numerical_cause_resolved=False, timing_envelope_adopted=False,
        numerical_domain_enclosure_qualified=False, physical_timing_qualified=False,
        release_qualified=False, scope=__doc__))
    print(json.dumps(dict(ngspice=measured, xyce={k: reference[k] for k in measured}, slot_guard=guard), indent=2))


if __name__ == '__main__':
    main()
