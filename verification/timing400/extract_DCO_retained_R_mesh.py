#!/usr/bin/env python3
"""Extract an isolated DCO R mesh with geometric reductions explicitly disabled.

Check default-tool equivalence first, original pre-R C and devices, and all MOS
model/geometry parameters against the default R export. Retain zero/self-loop
branches explicitly in the audit. Mesh topology and spatial C must be qualified
separately; no runtime deck is adopted here.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from audit_active_dco_rc_capacitance import parse, terminals
from check_compact_clock_tree import verify
from check_magic_cap_clip_windows import native
from check_isolated_magic_stock_v3 import devices
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    proof = base/'DCO_retained_R_mesh_default_controls_001/assessment.json'
    assert verify(proof)['R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming']
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    isolated = ROOT/'build/timing400/magic_retained_R_mesh_623_001/bin/magic'
    private = ROOT/'build/timing450/pdk/sky130A'
    rc = private/'libs.tech/magic/sky130A.magicrc'
    tech = private/'libs.tech/magic/sky130A.tech'
    reference = proof.parent/'trace'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    out = base/'DCO_retained_R_mesh_001'
    out.mkdir(exist_ok=False)
    target = out/'trace'
    target.mkdir()
    task = target/'extract.tcl'
    task.write_text((reference/'extract.tcl').read_text().replace(str(reference), str(target)))
    paths = [Path(__file__).resolve(), proof, owner, isolated, rc, tech, gds, task,
        Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),
        reference/(top+'.rcx.spice'), reference/(top+'.ext')]
    pins = {str(p): sha(p) for p in paths}
    env = dict(os.environ, PDK_ROOT=str(private.parent))
    for flag in ['OPENPLL_CAP_RC_SUBSTRATE', 'OPENPLL_CAP_TRACE_SUPPORT', 'OPENPLL_CAP_TRACE_FILE', 'OPENPLL_CAP_CLIP_INTERNAL']:
        env.pop(flag, None)
    env.update(OPENPLL_R_RETAIN_MESH='1', OPENPLL_R_NODE_TRACE_FILE=str(target/'R_provenance.log'),
               OPENPLL_R_SEGMENT_TRACE_FILE=str(target/'R_segments.log'))
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner), deadline_uptime=deadline, total_budget_restarted=False, automatic_identical_retry=False))
    with (target/'extract.log').open('x') as log, (target/'diagnostics.log').open('x') as errors:
        child = subprocess.Popen([str(isolated), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)],
            cwd=target, env=env, stdout=log, stderr=errors, start_new_session=True)
        save(out/'status.json', dict(state='native_retained_R_mesh_running', native_pid=child.pid, release_qualified=False))
        try:
            code = child.wait(timeout=min(600, max(0, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            save(out/'status.json', dict(state='timeout_inconclusive', release_qualified=False))
            return
    assert code == 0 and 'R_NODE_TRACE_EXTRACTION_COMPLETE' in (target/'extract.log').read_text()
    old, new = parse(reference/(top+'.rcx.spice')), parse(target/(top+'.rcx.spice'))
    assert old['ports'] == new['ports'] and old['X'].keys() == new['X'].keys()
    for name, row in old['X'].items():
        n = terminals(row)
        assert n == terminals(new['X'][name]) and row[n:] == new['X'][name][n:], name
    first, fa, _ = native(reference/(top+'.ext'))
    second, sa, _ = native(target/(top+'.ext'))
    assert all(abs(second.get(k, 0)-first.get(k, 0)) <= fa.get(k, 0)+sa.get(k, 0) for k in first.keys() | second.keys())
    assert devices(reference/(top+'.ext')) == devices(target/(top+'.ext'))
    counts = Counter()
    for a, b, r in new['R']:
        counts['positive' if r > 0 else 'zero' if r == 0 else 'negative'] += 1
        if a == b:
            counts['self_loop'] += 1
    assert not counts['negative'] and len(new['R']) >= len(old['R'])
    for path, value in pins.items():
        assert sha(path) == value
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json', 'status.json']},
        native_CAD_runs_added=1, reduction_switch='OPENPLL_R_RETAIN_MESH',
        original_pre_RC_C_matrix_and_devices_preserved=True,
        exported_MOS_model_and_geometry_parameters_preserved=True, public_ports_preserved=True,
        default_wire_R_branches=len(old['R']), retained_wire_R_branches=len(new['R']),
        retained_R_branch_counts=dict(counts),
        R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming=False,
        R_graph_electrical_equivalence_qualified=False,
        backannotated_C_not_used=True, retained_mesh_C_placement_qualified=False,
        release_qualified=False, adopted=False, scope=__doc__))
    save(out/'status.json', dict(state='retained_R_mesh_extraction_terminal', release_qualified=False))
    print('Retained native R mesh:', len(new['R']), 'branches;', dict(counts), '; electrical and C placement qualification remains open.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        out = ROOT/'build/timing400/release_001/DCO_retained_R_mesh_001'
        if out.exists():
            save(out/'status.json', dict(state='failed', error=repr(error), release_qualified=False))
        raise
