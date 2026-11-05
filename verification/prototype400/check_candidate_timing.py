#!/usr/bin/env python3
"""Parallel routed timing diagnostics on the selected corrected digital macro.

Supplied libraries and assumed boundary loading do not qualify nominal15PVT,
final fill loading, recovery/removal, CDC or analog clock waveforms.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import re
import signal
import sys
import time
from common import ROOT, save, sha, verify
from candidate_macro import digital_views
sys.path.append(str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import lease, identity
sys.path.append(str(ROOT / 'verification/timing400'))
from check_compact_mapping import LIB, TECH, LEF, OPENROAD
from check_compact_routed_timing import normalize_spef


def constraints(source):
    marker = 'foreach left [all_clocks]'
    if source.count(marker) != 1 or source.count('-period 2.0 [get_ports PLLOUT]') != 1:
        raise ValueError('unknown placement constraint fixture')
    result = source.split(marker)[0].replace('-period 2.0 [get_ports PLLOUT]', '-period 2.5 [get_ports PLLOUT]')
    result = result.replace('# 500 MHz is a capacity screen, pending measured startup/tracking bounds.',
                            '# 400 MHz diagnostic; final clock/loading bounds remain unqualified.')
    result += '''# Preserve related fast/divided-clock paths; exclude only asynchronous groups.
foreach left [all_clocks] {foreach right [all_clocks] {
 set l [get_full_name $left];set r [get_full_name $right]
 if {$l eq $r} {continue}
 if {$l in {PLLOUT FINECLK} && $r in {PLLOUT FINECLK}} {continue}
 set_false_path -from $left -to $right
}}
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
'''
    return result


def parse_report(text):
    if any(token in text for token in ('Error:', 'STA-1648', 'STA-1650')):
        raise ValueError('timing execution or SPEF binding error')
    slacks = {}
    for block in text.split('Startpoint:')[1:]:
        group = re.search(r'Path Group: ([^\n]+)', block)
        kind = re.search(r'Path Type: (max|min)', block)
        slack = re.search(r'(-?\d+\.\d+)\s+slack', block)
        if group and kind and slack:
            key = f'{group[1]}:{kind[1]}'
            value = float(slack[1])
            slacks[key] = min(slacks.get(key, value), value)
    if not {'PLLOUT:max','PLLOUT:min','FINECLK:max','FINECLK:min'} <= slacks.keys():
        raise ValueError('missing fast-clock setup/hold checks')
    violations = [line.strip() for line in text.splitlines() if '(VIOLATED)' in line]
    annotation = {name: int(value) for value, name in re.findall(
        r'Found (\d+) (partially unannotated|unannotated) drivers', text)}
    return dict(slack_ns=slacks, reported_violations=violations,
                annotation_driver_counts=annotation,
                reported_checks_passed=all(v >= 0 for v in slacks.values()) and not violations
                and set(annotation)=={'unannotated','partially unannotated'} and not any(annotation.values()))


def task(job):
    label, out, script, deadline = job
    out = Path(out)
    with lease(4, 4, deadline):
        execute([OPENROAD, '-no_init', '-exit', script], out / (label + '.log'), deadline, 4)
    return label


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'checks', 'placement', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    a = p.parse_args()
    route, placement, out = (x.resolve() for x in (a.route, a.placement, a.output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, jobs=a.jobs, internal_threads_per_job=4, automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, release_qualified=False,
             observed_utc=datetime.now(timezone.utc).isoformat(), **kw))

    def snapshot(paths):
        return {str(p): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}

    def stage(jobs):
        with ProcessPoolExecutor(max_workers=a.jobs, mp_context=multiprocessing.get_context('spawn')) as pool:
            futures = [pool.submit(task, job) for job in jobs]
            try:
                for future in as_completed(futures):
                    status('native_stage_running', last_completed=future.result(),
                           completed_jobs=sum(f.done() for f in futures), total_jobs=len(jobs))
            except BaseException:
                for future in futures:
                    future.cancel()
                for path in out.glob('*.process.json'):
                    record = json.loads(path.read_text())
                    if identity(record['pid']) == record['birth']:
                        try: os.killpg(record['process_group'], signal.SIGTERM)
                        except ProcessLookupError: pass
                raise

    try:
        status('verifying_selected_digital_candidate')
        selected = digital_views(route, a.checks, placement)
        diode_dir = ROOT / 'build/timing400/release_001/antenna_diode_load_001'
        diode = json.loads((diode_dir / 'assessment.json').read_text())
        verify(diode['input_sha256']); verify(diode['artifacts'])
        if not diode['native_model_equivalence_revalidated']:
            raise ValueError('conditional diode load model not checked')
        auxiliary = diode_dir / 'antenna_diode_load.lib'
        supplied = {label: LIB.parent / ('sky130_fd_sc_hs__' + name + '.lib') for label, name in
                    (('tt_25C_1v80', 'tt_025C_1v80'), ('ff_n40C_1v95', 'ff_n40C_1v95'), ('ss_100C_1v60', 'ss_100C_1v60'))}
        rc_models = {rc: LIB.parents[3] / f'libs.tech/librelane/rules.openrcx.sky130A.{rc}.magic'
                     for rc in ('min', 'nom', 'max')}
        source_sdc = placement / 'diagnostic.sdc'
        sdc = out / 'diagnostic_400.sdc'; sdc.write_text(constraints(source_sdc.read_text()))
        paths = [Path(__file__).resolve(), Path(sys.executable), Path(OPENROAD), TECH, LEF,
                 route / 'route.odb', route / 'assessment.json', source_sdc, auxiliary,
                 diode_dir / 'assessment.json', *supplied.values(), *rc_models.values()]
        paths += [Path(__file__).with_name('candidate_macro.py'), Path(__file__).with_name('common.py'),
                  ROOT / 'verification/signoff400/compiled_charge_v2.py', ROOT / 'verification/signoff400/resources.py',
                  ROOT / 'verification/timing400/check_compact_routed_timing.py',
                  ROOT / 'verification/timing400/check_compact_mapping.py']
        initial = snapshot(paths)
        pins = dict(selected['evidence_sha256'], **{str(path): sha(path) for path in paths})
        pins[str(sdc)] = sha(sdc)
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        def header(library):
            return f'read_lef {TECH}\nread_lef {LEF}\nread_liberty {library}\nread_liberty {auxiliary}\nread_db {route}/route.odb\nset_thread_count 4\n'
        jobs = []
        for rc, model in rc_models.items():
            script = out / ('extract_' + rc + '.tcl')
            script.write_text(header(LIB) + f'''define_process_corner -ext_model_index 0 RCX_{rc.upper()}
extract_parasitics -ext_model_file {model} -corner 0
write_spef {out}/route.{rc}.spef
puts "DIAGNOSTIC_RCX_COMPLETE"
exit
''')
            jobs.append(('extract_' + rc, str(out), str(script), deadline))
        status('extracting_three_routed_rc_views'); stage(jobs)
        normalized = {}
        for rc in rc_models:
            raw = out / f'route.{rc}.spef'
            text, count = normalize_spef(raw.read_text())
            target = out / f'route.{rc}.normalized.spef'; target.write_text(text)
            pins[str(raw)] = sha(raw); pins[str(target)] = sha(target); normalized[rc] = count
        jobs = []
        for label, library in supplied.items():
            for rc in rc_models:
                name = label + '_' + rc; script = out / (name + '.tcl')
                script.write_text(header(library) + f'''source {sdc}
set_propagated_clock [all_clocks]
read_spef {out}/route.{rc}.normalized.spef
report_parasitic_annotation -report_unannotated
report_checks -path_delay max -group_path_count 5 -digits 6
report_checks -path_delay min -group_path_count 5 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
check_setup -verbose
puts "DIAGNOSTIC_TIMING_COMPLETE"
exit
''')
                jobs.append((name, str(out), str(script), deadline))
        status('screening_nine_supplied_view_rc_cases'); stage(jobs)
        results = {}
        for name, _, _, _ in jobs:
            text = (out / (name + '.log')).read_text()
            if 'DIAGNOSTIC_TIMING_COMPLETE' not in text:
                raise ValueError('timing execution incomplete')
            results[name] = parse_report(text)
        verify(pins)
        if initial != snapshot(paths):
            raise ValueError('timing input changed during check')
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in out.iterdir() if path.is_file() and path.name != 'status.json'},
             results=results, spef_name_entries_normalized=normalized,
             target_mhz=400, reference_mhz=25, related_fast_and_divided_clock_paths_timed=True,
             supplied_views=list(supplied), all_reported_checks_passed=all(r['reported_checks_passed'] for r in results.values()),
             output_load_assumption_pf=0.005, uncertainty_assumption_ns=0.15,
             asynchronous_groups_excluded=True, external_reset_excluded=True,
             diode_load_view_conditional=True, final_parent_fill_and_interface_loading_included=False,
             nominal_15pvt_qualified=False, digital_timing_qualified=False,
             physical_timing_qualified=False, release_qualified=False, diagnostic=True))
        status('timing_diagnostic_terminal')
    except BaseException as error:
        status('failed', reason=repr(error)); raise


if __name__ == '__main__':
    main()
