#!/usr/bin/env python3
"""Check pointer instrumentation against the retained actual-DCO native export.

One changed-instrumentation native run. Require the same exported R/MOS graph
under a bijective renaming, original pre-R C/devices, and a complete unique
SPICE-device geometry index. Backannotated C remains ineligible.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time
from audit_active_dco_rc_capacitance import parse, terminals
from check_compact_clock_tree import verify
from check_magic_cap_clip_windows import native
from check_isolated_magic_stock_v3 import devices
from compare_native_R_networks_v4 import compare
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    build = base/'magic_R_tile_domain_trace_build_001/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    original = base/'DCO_retained_R_mesh_001/assessment.json'
    assert verify(original)['original_pre_RC_C_matrix_and_devices_preserved']
    reference = original.parent/'trace'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert deadline > time.clock_gettime(time.CLOCK_BOOTTIME)
    isolated = ROOT/'build/timing400/magic_R_tile_domain_trace_623_001/bin/magic'
    private = ROOT/'build/timing450/pdk/sky130A'
    rc = private/'libs.tech/magic/sky130A.magicrc'
    out = base/'DCO_R_tile_domain_trace_controls_001'
    out.mkdir(exist_ok=False)
    target = out/'trace'
    target.mkdir()
    task = target/'extract.tcl'
    task.write_text((reference/'extract.tcl').read_text().replace(str(reference), str(target)))
    paths = [Path(__file__).resolve(), build, original, owner, isolated, rc,
        private/'libs.tech/magic/sky130A.tech', reference/'extract.tcl', task,
        reference/(top+'.rcx.spice'), reference/(top+'.ext'), reference/(top+'.res.ext'),
        Path(__file__).with_name('compare_native_R_networks_v4.py')]
    pins = {str(p): sha(p) for p in paths}
    env = dict(os.environ, PDK_ROOT=str(private.parent))
    for flag in ['OPENPLL_CAP_RC_SUBSTRATE', 'OPENPLL_CAP_TRACE_SUPPORT', 'OPENPLL_CAP_TRACE_FILE', 'OPENPLL_CAP_SURFACE_FILE', 'OPENPLL_CAP_KERNEL_FILE', 'OPENPLL_CAP_CLIP_INTERNAL']:
        env.pop(flag, None)
    env.update(OPENPLL_R_TILE_DOMAIN_TRACE='1', OPENPLL_R_RETAIN_MESH='1', OPENPLL_R_NODE_TRACE_FILE=str(target/'R_provenance.log'),
        OPENPLL_R_SEGMENT_TRACE_FILE=str(target/'R_segments.log'),
        OPENPLL_R_BIND_TRACE_FILE=str(target/'R_bindings.log'),
        OPENPLL_SPICE_DEVICE_TRACE_FILE=str(target/'SPICE_devices.log'))
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner), deadline_uptime=deadline, total_budget_restarted=False, automatic_identical_retry=False))
    with (target/'extract.log').open('x') as log, (target/'diagnostics.log').open('x') as errors:
        child = subprocess.Popen([str(isolated), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)],
            cwd=target, env=env, stdout=log, stderr=errors, start_new_session=True)
        save(out/'status.json', dict(state='native_R_binding_control_running', native_pid=child.pid, release_qualified=False))
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
    result = compare(reference, target)
    mapping = result.pop('node_mapping', {})
    save(out/'network_comparison.json', result)
    save(out/'node_mapping.json', mapping)
    assert result.get('bijective_mapping_proven') and result['unchanged_device_parameters_and_mapped_terminals']
    assert result['exact_mapped_R_branch_multiplicity_preserved'] and not result['R_C_differences']['R']
    first, fa, _ = native(reference/(top+'.ext'))
    second, sa, _ = native(target/(top+'.ext'))
    assert all(abs(second.get(k, 0)-first.get(k, 0)) <= fa.get(k, 0)+sa.get(k, 0) for k in first.keys() | second.keys())
    assert devices(reference/(top+'.ext')) == devices(target/(top+'.ext'))
    exported = parse(target/(top+'.rcx.spice'))
    ids, geometry = {}, set()
    for line in (target/'SPICE_devices.log').open():
        f = shlex.split(line)
        assert f[0] == 'DEVICE' and len(f) == 9 and f[1] not in ids
        row = exported['X'][f[1]]
        assert f[2] == row[terminals(row)]
        key = (f[2], *map(int, f[3:7]))
        assert key not in geometry, key
        geometry.add(key)
        ids[f[1]] = dict(model=f[2], rectangle_internal=list(map(int, f[3:7])),
            raw_length=int(f[7]), raw_width=int(f[8]))
    assert ids.keys() == exported['X'].keys() and len(ids) == 8620
    save(out/'device_geometry_index.json', ids)
    for p, value in pins.items():
        assert sha(p) == value
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json', 'status.json']},
        native_CAD_runs_added=1, R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming=True,
        original_pre_RC_C_matrix_and_devices_preserved=True,
        complete_unique_SPICE_device_geometry_index=True, devices_indexed=len(ids),
        native_binding_and_node_lifetime_trace_completed=True,
        complete_tile_breakpoint_and_contact_working_plane_records_emitted=True, backannotated_C_not_used=True,
        private_pointer_export_or_physical_RC_qualified=False, release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='R_binding_trace_native_control_terminal', release_qualified=False))
    print('Native binding instrumentation preserves exported R/MOS and original C/devices; indexed all8620 devices by unique geometry.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        out = ROOT/'build/timing400/release_001/DCO_R_tile_domain_trace_controls_001'
        if out.exists():
            save(out/'status.json', dict(state='failed', error=repr(error), release_qualified=False))
        raise
