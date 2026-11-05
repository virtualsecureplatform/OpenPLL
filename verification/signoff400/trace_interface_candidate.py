#!/usr/bin/env python3
"""Separate full-layout diagnostic of the unadopted rectangular-interface fix.

Retains local SSD artifacts, exact native pre-R card comparisons and subsequent
snapshot/geometry audits. Never replaces the running original campaign.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from common import ROOT, save, sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease, identity

CAD = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',
       str(ROOT/'build/apptainer/openpll-release-modern.sif')]
CAD_PYTHON = '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
TOP = 'Prototype400_FilledCapacitanceView'


def run(build, control, reference, output):
    build, control, reference, out = (Path(p).resolve() for p in (build, control, reference, output))
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-interface-domain-', dir='/tmp'))
    domain, trace = scratch/'domain', scratch/'domain/trace'
    trace.mkdir(parents=True)
    (out/'domain').symlink_to(domain, target_is_directory=True)
    save(domain/'owner.json', dict(pid=os.getpid(), started_utc=started, budget_started_utc=started,
        wall_limit_s=43200, automatic_identical_retry=False,
        changed_algorithm='rectangular_interface_and_label_origin_construction',
        original_campaign_unchanged=True, local_trace_retained=True))
    save(out/'owner.json', dict(pid=os.getpid(), started_utc=started, native_wall_limit_s=43200,
        automatic_identical_retry=False, original_campaign_unchanged=True, retained_scratch=str(scratch)))
    def status(state, **extra):
        save(out/'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             release_qualified=False, **extra))
    def domain_status(state, **extra):
        save(domain/'status.json', dict(state=state, release_qualified=False, **extra))
        status(state, **extra)
    try:
        b, c, r = (json.loads((p/'assessment.json').read_text()) for p in (build, control, reference))
        if not b['experimental_rectangular_device_interface_build_completed'] or not c['partial_diffusion_native_control_passed']:
            raise ValueError('completed isolated build and driven device-interface control required')
        if c['input_sha256'].get(str(build/'assessment.json')) != sha(build/'assessment.json'):
            raise ValueError('native control/build identity mismatch')
        for table in (b['input_sha256'], b['diagnostic_source_files'], c['artifacts']):
            for p, h in table.items():
                if sha(p) != h:
                    raise ValueError('experimental source/control input changed: '+p)
        views = [Path(p) for p in r['input_sha256'] if p.endswith('/loading/capacitance_view.gds')]
        if len(views) != 1:
            raise ValueError('unique exact filled reference view required')
        view = views[0]
        if sha(view) != r['input_sha256'][str(view)]:
            raise ValueError('reference filled view changed')
        if shutil.disk_usage('/tmp').free < 64*1024**3:
            raise ValueError('local trace reserve unavailable')
        local_view = scratch/'capacitance_view.gds'
        shutil.copyfile(view, local_view)
        if sha(local_view) != sha(view):
            raise ValueError('staged GDS bytes differ')
        prefix = Path(b['prefix'])
        binary = prefix/'bin/magic'
        library = prefix/'lib/magic/tcl/tclmagic.so'
        for p in (binary, library):
            if sha(p) != b['artifacts'][str(p)]:
                raise ValueError('native binary/library differs from completed build')
        task = trace/'extract.tcl'
        task.write_text((reference/'trace/extract.tcl').read_text().replace(str(reference/'trace'), str(trace)).replace(str(view), str(local_view)))
        tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
        rc = tech.with_name('sky130A.magicrc')
        paths = [build/'assessment.json', control/'assessment.json', reference/'assessment.json',
            binary, library, task, local_view, view, rc, tech, reference/'trace/extract.tcl',
            reference/'trace/pre_resistance.spice', reference/'trace'/(TOP+'.ext'), Path(__file__).resolve(),
            *[Path(__file__).with_name(n) for n in ('common.py', 'compiled_charge.py', 'parallel_hash.py', 'resources.py')]]
        pins = {str(p): sha(p) for p in paths}
        save(domain/'input_manifest.json', dict(input_sha256=pins, experimental_native_backend=True,
             local_GDS_bytes_equal_reference=True, original_campaign_unchanged=True))
        env = {k: v for k, v in os.environ.items() if not k.startswith('OPENPLL_CAP_')}
        env.update(PDK_ROOT=str(ROOT/'build/timing450/pdk'), OPENPLL_R_TILE_DOMAIN_TRACE='1',
            OPENPLL_R_RETAIN_MESH='1', OPENPLL_R_NODE_TRACE_FILE=str(trace/'R_provenance.log'),
            OPENPLL_R_SEGMENT_TRACE_FILE=str(trace/'R_segments.log'), OPENPLL_R_BIND_TRACE_FILE=str(trace/'R_bindings.log'),
            OPENPLL_SPICE_DEVICE_TRACE_FILE=str(trace/'SPICE_devices.log'))
        def limits():
            cap = 48*1024**3
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        with lease(1, 48, deadline), (trace/'extract.log').open('x') as log:
            command = CAD+[str(binary), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)]
            child = subprocess.Popen(command, cwd=trace, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, preexec_fn=limits)
            save(domain/'native_process.json', dict(pid=child.pid, birth=identity(child.pid), process_group=child.pid,
                 command=command, deadline_uptime=deadline, memory_limit_GiB=48))
            domain_status('experimental_full_layout_native_R_running', native_pid=child.pid)
            try:
                code = child.wait(timeout=max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except BaseException:
                os.killpg(child.pid, signal.SIGTERM)
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
                raise
            if code != 0 or 'FILLED_RETAINED_RC_NATIVE_COMPLETE' not in (trace/'extract.log').read_text():
                raise ValueError('experimental native trace failed or incomplete')
        comparator = ROOT/'build/signoff400/startup_timing_native_card_comparison_002/compare_native_cards'
        proof = comparator.parent/'assessment.json'
        if sha(comparator) != json.loads(proof.read_text())['artifacts'][str(comparator)]:
            raise ValueError('validated native-card comparator changed')
        pins[str(proof)], pins[str(comparator)] = sha(proof), sha(comparator)
        with lease(16, 12, deadline):
            domain_status('experimental_native_pre_R_C_and_device_equivalence')
            cfg = domain/'card_comparison_config.json'
            save(cfg, dict(left_spice=str(reference/'trace/pre_resistance.spice'), right_spice=str(trace/'pre_resistance.spice'),
                left_ext=str(reference/'trace'/(TOP+'.ext')), right_ext=str(trace/(TOP+'.ext')),
                deadline_uptime=deadline, threads=16))
            execute([comparator, cfg], domain/'card_comparison.log', deadline, 12)
            card = json.loads((domain/'card_comparison.log').read_text())
            if not card['exact_Decimal_fold_matrix_equality_implied']:
                raise ValueError('full pre-R C/device proof incomplete')
        counts = {k: 0 for k in ('R', 'C', 'X', 'M')}
        with (trace/'retained_rc.spice').open(buffering=8*1024**2) as stream:
            for line in stream:
                if line[:1].upper() in counts:
                    counts[line[0].upper()] += 1
        if not counts['R'] or not counts['C'] or not counts['X']+counts['M']:
            raise ValueError('empty retained native circuit')
        with lease(8, 8, deadline):
            domain_status('hashing_complete_local_experimental_trace')
            from concurrent.futures import ThreadPoolExecutor
            files = [p for p in trace.rglob('*') if p.is_file()]
            with ThreadPoolExecutor(max_workers=8) as pool:
                hashes = list(pool.map(lambda p: sha_prefetch(p, readers=2, deadline=deadline), files))
            artifacts = {str(p): h for p, h in zip(files, hashes)}
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('experimental input changed: '+p)
        save(domain/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
            native_rc_export_completed=True, retained_native_cards=counts, pre_resistance_capacitance_preserved=True,
            domain_creation_records_preserved=True, all_wire_domains_reconciled=False,
            signed_capacitance_attachment_qualified=False, fom_substrate_coverage_qualified=False,
            physical_domain_complete=False, prototype_handoff_qualified=False, release_qualified=False,
            experimental_backend_unadopted=True, local_trace_retained=True))
        domain_status('retained_rc_native_terminal_pending_domain_reconciliation')
        index = scratch/'domain_index'
        (out/'domain_index').symlink_to(index, target_is_directory=True)
        status('indexing_new_experimental_R_domains')
        with lease(4, 32, time.clock_gettime(time.CLOCK_BOOTTIME)+43200):
            execute(CAD+[CAD_PYTHON, ROOT/'verification/prototype400/index_filled_domain_v4.py',
                '--domain', domain, '--original-owner', domain/'owner.json', '--output', index], out/'index.log',
                time.clock_gettime(time.CLOCK_BOOTTIME)+43200, 32)
        geometry = scratch/'r_registration'
        (out/'r_registration').symlink_to(geometry, target_is_directory=True)
        status('auditing_new_experimental_full_R_geometry')
        execute([sys.executable, ROOT/'verification/signoff400/audit_r_geometry_v5.py', '--index', index,
            '--native', trace/'R_provenance.log', '--segments', trace/'R_segments.log', '--output', geometry],
            out/'registration.log', time.clock_gettime(time.CLOCK_BOOTTIME)+43200, 16)
        status('experimental_R_geometry_diagnostic_complete_physical_RC_pending')
    except BaseException as exc:
        status('failed', reason=repr(exc), retained_scratch=str(scratch))
        raise


if __name__ == '__main__':
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'control', 'reference', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    run(a.build, a.control, a.reference, a.output)
