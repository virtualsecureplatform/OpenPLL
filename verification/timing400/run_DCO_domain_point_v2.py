#!/usr/bin/env python3
"""One bounded golden-Xyce diagnostic on a checked complete-domain candidate.

No legacy frequency result is reused. The ideal point-feed wrapper and optional
explicit external capacitor are diagnostic assumptions, not full integration
qualification. Shared admission/deadline include preparation and queue time.
"""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

from compile_local_C_operators_v2 import digest, save


def live_engines():
    found = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                state = (p/'stat').read_text().rsplit(')', 1)[1].split()[0]
                if state != 'Z':
                    found.append(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return found


def model_files(first, deadline):
    pending, seen = [first], set()
    while pending:
        path = pending.pop().resolve()
        if path in seen:
            continue
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        assert path.is_file(), path
        seen.add(path)
        for line in path.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith('*'):
                continue
            if s.split()[0].lower() not in ['.include', '.inc', '.lib']:
                continue
            tokens = shlex.split(s)
            if tokens[0].lower() == '.lib' and len(tokens) == 2:
                continue
            assert len(tokens) >= 2
            dependency = (path.parent/tokens[1]).resolve()
            assert dependency.is_file(), (path, tokens)
            pending.append(dependency)
    return sorted(seen)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--coarse', type=int, required=True)
    parser.add_argument('--fine', type=int, required=True)
    parser.add_argument('--corner', choices=['tt', 'ff', 'ss', 'sf', 'fs'], default='tt')
    parser.add_argument('--temperature', type=int, choices=[-40, 27, 125], default=27)
    parser.add_argument('--duration-ns', type=float, default=80.)
    parser.add_argument('--measure-start-ns', type=float, default=20.)
    parser.add_argument('--max-step-ps', type=float, default=10.)
    parser.add_argument('--reltol', type=float, default=1e-5)
    parser.add_argument('--abstol', type=float, default=1e-9)
    parser.add_argument('--external-cap-ff', type=float, default=0.)
    args = parser.parse_args()
    assert 0 <= args.coarse <= 47 and 8 <= args.fine <= 247
    assert 5 < args.measure_start_ns < args.duration_ns
    assert all(math.isfinite(v) and v > 0 for v in [args.duration_ns, args.max_step_ps, args.reltol, args.abstol])
    assert math.isfinite(args.external_cap_ff) and args.external_cap_ff >= 0
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    proof_path = args.candidate/'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['source_matrix_numerical_passivity_check_passed'] and proof['signed_matrix_branch_realization_readback_passed']
    ports = proof['public_port_names']
    expected = {'VPWR', 'VGND', 'VPB', 'VNB', 'PLLOUT', 'RESET_N'} | {f'DCO_THERM[{i}]' for i in range(255)} | {f'COARSETHERMAL_CODE[{i}]' for i in range(47)}
    assert len(ports) == 308 and set(ports) == expected
    circuit = args.candidate/'candidate_unqualified.spice'
    assert digest(circuit) == proof['artifacts'][str(circuit.resolve())]
    args.output.mkdir(exist_ok=False)
    save(args.output/'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(), runner_pid=os.getpid(),
        original_owner=str(owner), deadline_uptime=deadline, budget_restarted=False, identical_native_retry=False))
    def status(state, **more):
        save(args.output/'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline, **more))
    status('preparing_checked_candidate')
    pdk = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    model = pdk/'sky130.lib.spice'
    binary = Path('/opt/xyce/bin/Xyce')
    files = model_files(model, deadline)
    lines = ['* Unqualified complete-domain DCO diagnostic; frozen1.8V supply scope.',
        f'.lib "{model}" {args.corner}', f'.include "{circuit.resolve()}"',
        'VVPWR VPWR 0 1.8', 'VVGND VGND 0 0', 'VVPB VPB 0 1.8', 'VVNB VNB 0 0',
        f'VRESET RESET_N 0 PULSE(0 1.8 5n 50p 50p {args.duration_ns:g}n {2*args.duration_ns:g}n)']
    for i in range(255):
        lines.append(f'VFINE_{i} DCO_THERM[{i}] 0 '+('1.8' if i >= args.fine else '0'))
    for i in range(47):
        lines.append(f'VCOARSE_{i} COARSETHERMAL_CODE[{i}] 0 '+('1.8' if i < args.coarse else '0'))
    lines.append('XDCO')
    connections = ports+[proof['diagnostic_wrapper']]
    lines.extend('+ '+' '.join(connections[i:i+8]) for i in range(0, len(connections), 8))
    if args.external_cap_ff:
        lines.append(f'CEXPLICIT_EXTERNAL PLLOUT VGND {args.external_cap_ff*1e-15:.17g}')
    lines.extend([f'.options DEVICE TEMP={args.temperature}',
        f'.options TIMEINT RELTOL={args.reltol:g} ABSTOL={args.abstol:g}',
        f'.tran 20p {args.duration_ns:g}n 0 {args.max_step_ps:g}p',
        '.print TRAN FORMAT=CSV V(PLLOUT) I(VVPWR)', '.end'])
    deck = args.output/'point.cir'
    deck.write_text('\n'.join(lines)+'\n')
    inputs = [Path(__file__).resolve(), owner, proof_path, circuit, deck, binary, *files]
    pins = {str(p.resolve()): digest(p) for p in inputs}
    params = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    save(args.output/'input_manifest.json', dict(input_sha256=pins, parameters=params,
        simulator='upstream Xyce7.10', external_load_scope='Explicit added capacitor only; no full-parent loading qualification',
        point_feed_assumptions=proof['assumptions']))
    while True:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive_before_native')
            return
        with (base.parent/'guarded_native_admission.lock').open('a+') as admission:
            fcntl.flock(admission, fcntl.LOCK_EX)
            active = live_engines()
            if len(active) < 4:
                with (args.output/'native.log').open('x') as log:
                    child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())], cwd=pdk,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
                status('native_point_running', native_pid=child.pid, previous_engines=active)
                break
            status('queued_for_native_slot', observed_engines=active)
        time.sleep(1.)
    try:
        code = child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        status('timeout_inconclusive')
        return
    wave = Path(str(deck)+'.csv')
    metrics = None
    if code == 0 and wave.exists():
        with wave.open() as stream:
            records = list(csv.DictReader(stream))
        times = [float(r['TIME']) for r in records]
        values = [float(r['V(PLLOUT)']) for r in records]
        assert all(math.isfinite(v) for v in times+values) and all(a < b for a, b in zip(times, times[1:]))
        assert times[-1] >= args.duration_ns*1e-9*(1-1e-7)
        edges = []
        for i in range(1, len(times)):
            if values[i-1] < .9 <= values[i]:
                t = times[i-1]+(.9-values[i-1])*(times[i]-times[i-1])/(values[i]-values[i-1])
                if t >= args.measure_start_ns*1e-9:
                    edges.append(t)
        if len(edges) >= 4:
            metrics = dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6, periods=len(edges)-1,
                output_min_V=min(values), output_max_V=max(values))
    artifacts = [p for p in args.output.iterdir() if p.is_file() and p.name not in ['assessment.json', 'status.json']]
    assert all(digest(Path(p)) == value for p, value in pins.items())
    result = dict(native_exit=code, completed_diagnostic_oscillation=metrics is not None, metrics=metrics,
        parameters=params, settled_frequency_calibration_qualified=False, physical_full_parent_loading_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256=pins, artifacts={str(p.resolve()): digest(p) for p in artifacts})
    save(args.output/'assessment.json', result)
    status('completed' if metrics is not None else 'native_or_oscillation_nonpass', native_exit=code, metrics=metrics)
    print(json.dumps(dict(native_exit=code, metrics=metrics), indent=2))


if __name__ == '__main__':
    main()
