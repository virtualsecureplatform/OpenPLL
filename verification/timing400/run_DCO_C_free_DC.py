#!/usr/bin/env python3
"""Obtain exact constant-capacitor-free DCO DC bias, without a dynamic model change.

Keep all resistors, nonlinear devices, point feeds and stimulus. Only constant
CFIELD capacitors are open in DC. This run is a new DC-only diagnostic, not a
repeat of the active full-C transient or a release qualification.
"""
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines, model_files


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    controls = base/'split_DC_initialization_controls_001/assessment.json'
    assert json.loads(controls.read_text())['native_saved_IC_UIC_linear_and_BSIM_transient_control_passed']
    candidate = base/'DCO_domain_candidate_nom_001'
    source = candidate/'candidate_unqualified.spice'
    proof_path = candidate/'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert digest(source) == proof['artifacts'][str(source.resolve())]
    prior = base/'DCO_domain_nom_tt27_c0_f247_80ns_klu_001/point.cir'
    out = base/'DCO_domain_nom_tt27_c0_f247_C_free_DC_001'
    out.mkdir(exist_ok=False)
    def status(state, **more):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline, **more))
    status('preparing_exact_DC_equations')
    reduced = out/'C_free_DC_only.spice'
    removed = kept = 0
    with source.open() as stream, reduced.open('x') as dest:
        for line in stream:
            if line.startswith('CFIELD_'):
                tokens = line.split()
                assert len(tokens) == 4 and tokens[0] == f'CFIELD_{removed+1}'
                assert math.isfinite(float(tokens[3])) and float(tokens[3]) != 0
                removed += 1
            else:
                dest.write(line)
                kept += 1
            if (removed+kept) % 100000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    assert removed == proof['capacitor_branches']
    # Independent readback establishes every retained line, including all
    # nonlinear device parameters, is byte-identical and in the same order.
    with source.open() as original, reduced.open() as result:
        for line in original:
            if not line.startswith('CFIELD_'):
                assert result.readline() == line
        assert result.read() == ''
    bias = out/'operating.ic'
    lines = prior.read_text().splitlines()
    assert sum(line.startswith('.tran ') for line in lines) == 1
    assert sum(line.startswith('.include ') for line in lines) == 1
    replacements = {
        f'.include "{source.resolve()}"': f'.include "{reduced.resolve()}"',
        next(line for line in lines if line.startswith('.tran ')): '.dc VVPWR 1.8 1.8 0.1',
        '.print TRAN FORMAT=CSV V(PLLOUT) I(VVPWR)': '.print DC FORMAT=STD PRECISION=16 V(PLLOUT) I(VVPWR)',
        '.end': f'.SAVE TYPE=IC FILE={bias.resolve()}\n.end',
    }
    assert all(k in lines for k in replacements)
    deck = out/'point.cir'
    deck.write_text('\n'.join(replacements.get(line, line) for line in lines)+'\n')
    pdk = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    binary = Path('/opt/xyce/bin/Xyce')
    inputs = [Path(__file__).resolve(), owner, controls, proof_path, source, prior, reduced, deck, binary,
              *model_files(pdk/'sky130.lib.spice', deadline)]
    pins = {str(p.resolve()): digest(p) for p in inputs}
    save(out/'input_manifest.json', dict(input_sha256=pins,
        linear_capacitors_removed_for_DC_only=removed, retained_lines_byte_identical=True,
        nonlinear_devices_and_all_R_preserved=True, original_deadline_reused=True,
        dynamic_model_changed=False, identical_native_retry=False))
    while True:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive_before_native')
            return
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            active = live_engines()
            if len(active) < 4:
                with (out/'native.log').open('x') as log:
                    child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                        cwd=pdk, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
                status('native_DC_running', native_pid=child.pid, previous_engines=active)
                break
        time.sleep(1)
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
    passed = code == 0 and bias.exists() and bias.stat().st_size > 0
    assert all(digest(Path(p)) == value for p, value in pins.items())
    artifacts = [p for p in out.iterdir() if p.is_file() and p.name not in ['status.json', 'assessment.json']]
    save(out/'assessment.json', dict(native_exit=code, exact_C_free_DC_bias_completed=passed,
        constant_capacitors_removed_for_DC_only=removed, retained_lines_byte_identical=True,
        saved_bias_matches_full_C_native_solve_verified=False, full_C_DCO_startup_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256=pins, artifacts={str(p.resolve()): digest(p) for p in artifacts}))
    status('completed' if passed else 'native_DC_nonpass', native_exit=code)


if __name__ == '__main__':
    main()
