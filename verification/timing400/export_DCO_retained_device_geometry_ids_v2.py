#!/usr/bin/env python3
"""Index original pre-R DCO device parameters by native physical geometry.

Read the retained .ext and .res.ext directly: no GDS extraction or wire pass is repeated.
Require the original full C and device cards, including global junction records,
to be preserved before using the geometry IDs for a replacement model.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import time
from audit_active_dco_rc_capacitance import parse, terminals
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    build = base/'magic_R_binding_trace_build_003/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert deadline > time.clock_gettime(time.CLOCK_BOOTTIME)
    original = base/'DCO_R_binding_trace_controls_001/trace/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.rcx.spice'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = base/'DCO_R_binding_trace_controls_001/trace'/(top+'.ext')
    isolated = ROOT/'build/timing400/magic_R_binding_trace_623_003/bin/magic'
    private = ROOT/'build/timing450/pdk/sky130A'
    rc = private/'libs.tech/magic/sky130A.magicrc'
    out = base/'DCO_retained_device_geometry_ids_002'
    out.mkdir(exist_ok=False)
    copied = out/(top+'.ext')
    shutil.copyfile(ext, copied)
    resistance = ext.with_name(top+'.res.ext')
    copied_resistance = out/(top+'.res.ext')
    shutil.copyfile(resistance, copied_resistance)
    assert not any(l.startswith('use ') for l in copied.open())
    task = out/'export.tcl'
    target = out/'original.spice'
    task.write_text('''drc off
crashbackups disable
locking disable
if {[catch {
extract style ngspice()
ext2spice lvs
ext2spice cthresh 0.01
ext2spice extresist on
ext2spice -f ngspice -o "'''+str(target)+'" "'+str(copied)+'''"
puts "ORIGINAL_DEVICE_GEOMETRY_EXPORT_COMPLETE"
} error]} {puts stderr $error; exit 1}
exit 0
''')
    paths = [Path(__file__).resolve(), owner, build, original, ext, copied, resistance, copied_resistance, task, isolated, rc,
             private/'libs.tech/magic/sky130A.tech', Path(__file__).with_name('audit_active_dco_rc_capacitance.py')]
    pins = {str(p): sha(p) for p in paths}
    env = dict(os.environ, PDK_ROOT=str(private.parent))
    for name in list(env):
        if name.startswith('OPENPLL_'):
            env.pop(name)
    env['OPENPLL_SPICE_DEVICE_TRACE_FILE'] = str(out/'SPICE_devices.log')
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner), deadline_uptime=deadline, total_budget_restarted=False, automatic_identical_retry=False))
    with (out/'export.log').open('x') as log, (out/'diagnostics.log').open('x') as errors:
        child = subprocess.Popen([str(isolated), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)],
            cwd=out, env=env, stdout=log, stderr=errors, start_new_session=True)
        save(out/'status.json', dict(state='retained_device_geometry_export_running', native_pid=child.pid, release_qualified=False))
        try:
            code = child.wait(timeout=min(120, max(0, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            save(out/'status.json', dict(state='timeout_inconclusive', release_qualified=False))
            return
    assert code == 0 and 'ORIGINAL_DEVICE_GEOMETRY_EXPORT_COMPLETE' in (out/'export.log').read_text()
    a, b = parse(original), parse(target)
    assert a['ports'] == b['ports'] and a['X'] == b['X'] and Counter((tuple(sorted([x, y])), v) for x, y, v in a['R']) == Counter((tuple(sorted([x, y])), v) for x, y, v in b['R'])
    assert Counter((tuple(sorted([x, y])), v) for x, y, v in a['C']) == Counter((tuple(sorted([x, y])), v) for x, y, v in b['C'])
    ids, unique = {}, set()
    for line in (out/'SPICE_devices.log').open():
        f = shlex.split(line)
        assert f[0] == 'DEVICE' and len(f) == 9 and f[1] not in ids
        row = b['X'][f[1]]
        assert row[terminals(row)] == f[2]
        key = (f[2], *map(int, f[3:7]))
        assert key not in unique
        unique.add(key)
        ids[f[1]] = dict(model=f[2], rectangle_internal=list(map(int, f[3:7])),
            raw_length=int(f[7]), raw_width=int(f[8]), original_card=row)
    assert len(ids) == 8620 and ids.keys() == b['X'].keys()
    save(out/'device_geometry_index.json', ids)
    for path, value in pins.items():
        assert sha(path) == value
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.name not in ['owner.json', 'status.json']},
        native_GDS_extractions_added=0, native_R_passes_added=0, native_ext2spice_exports_added=1,
        retained_R_C_and_all_device_cards_preserved=True,
        retained_export_junction_records_preserved=True,
        complete_unique_retained_device_geometry_index=True, devices_indexed=len(ids),
        private_pointer_attachment_and_junction_distribution_qualified=False,
        release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='retained_device_geometry_export_terminal', release_qualified=False))
    print('Retained DCO R/C and8620 device cards preserved; unique geometry IDs exported without a GDS/R rerun.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        out = ROOT/'build/timing400/release_001/DCO_retained_device_geometry_ids_002'
        if out.exists():
            save(out/'status.json', dict(state='failed', error=repr(error), release_qualified=False))
        raise
