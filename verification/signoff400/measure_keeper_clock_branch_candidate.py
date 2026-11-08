"""Paired setup/hold diagnostics on the geometry-reused internal digital macro."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_routed_timing import normalize_spef
from compiled_charge_v2 import execute
from measure_selected_CDC_interstage_timing import result
from bind_CDC_physical_instances import word
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    reuse = b / 'selected_keeper_digital_macro_reuse_1439/assessment.json'
    candidate = b / 'selected_keeper_clock_branch_candidate_1452'
    candidate_receipt = candidate/'assessment.json'
    ca = json.loads(candidate_receipt.read_text())
    if ca.get('native_candidate_route_completed') is not True:raise ValueError('normally completed candidate route required')
    verify(ca['input_sha256']);verify(ca['artifacts'])
    classification = b / 'prototype_v3_selected_402p1_path_classification_019'
    cr = classification / 'assessment.json'
    rr, cc = [json.loads(p.read_text()) for p in [reuse, cr]]
    try:
        verify(rr['input_sha256'])
        verify(cc['input_sha256'])
        verify(cc['artifacts'])
        if rr['all_recursive_layer_geometry_and_texts_match'] is not True:
            raise ValueError('same current internal macro geometry required')
        samples = json.loads((classification / 'paths.json').read_text())
        pairs = sorted({(r['startpoint'], r['endpoint'], r['classification']) for r in samples if r['slack_ns'] < 0})
        if len(pairs) != 3:
            raise ValueError('expected three distinct retained critical path pairs')
        paths = [candidate_receipt,candidate/'route.odb',candidate/'route.min.spef',candidate/'route.max.spef',ROOT/'verification/timing400/check_compact_routed_timing.py',reuse, cr, classification / 'paths.json', Path(OPENROAD), Path(__file__).resolve(), Path(__file__).with_name('measure_selected_CDC_interstage_timing.py'), Path(__file__).with_name('bind_CDC_physical_instances.py')]
        pins = {str(p): sha(p) for p in paths}
        rows = []
        artifacts = {}
        for corner in ['tt', 'ff', 'ss', 'sf', 'fs']:
            base = b / ('prototype_v3_selected_402p1_timing_' + corner + '_019')
            receipt = base / 'assessment.json'
            value = json.loads(receipt.read_text())
            if cc['input_sha256'].get(str(receipt)) != sha(receipt):
                raise ValueError('classification/screen lineage mismatch')
            verify(value['artifacts'])
            original = base / 'fixed_divide16/screen.tcl'
            text = original.read_text()
            if text.count('report_parasitic_annotation') != 1:
                raise ValueError('one retained analysis prefix required')
            text = text.split('report_parasitic_annotation')[0]
            pins.update({str(receipt): sha(receipt), str(original): sha(original)})
            # Bind every retained library, database, SDC and SPEF actually read.
            for line in text.splitlines():
                if line.startswith(('read_liberty ', 'read_db ', 'source ', 'read_spef ')):
                    path = Path(line.split()[-1])
                    pins[str(path)] = sha(path)
            directory = output / corner
            directory.mkdir()
            normalized={}
            for wire in ['min','max']:
                fixed,count=normalize_spef((candidate/('route.'+wire+'.spef')).read_text())
                path=directory/('route.'+wire+'.normalized.spef');path.write_text(fixed);pins[str(path)]=sha(path);normalized[wire]=path
            updated=[]
            for line in text.splitlines():
                if line.startswith('read_db '):line='read_db '+str(candidate/'route.odb')
                elif line.startswith('read_spef -min '):line='read_spef -min '+str(normalized['min'])
                elif line.startswith('read_spef -max '):line='read_spef -max '+str(normalized['max'])
                updated.append(line)
            text='\n'.join(updated)+'\nreport_parasitic_annotation -report_unannotated\nreport_worst_slack -max\nreport_worst_slack -min\nreport_checks -path_delay min_max -group_path_count 100000 -endpoint_path_count 1 -slack_max 0 -digits 9\nreport_check_types -max_slew -max_capacitance -min_pulse_width -recovery -removal -violators -digits 9\ncheck_setup -verbose\n'
            for index, (start, target, kind) in enumerate(pairs):
                for delay in ['min', 'max']:
                    text += 'puts OPENPLL_PAIR_' + str(index) + '_' + delay + '_BEGIN\n'
                    text += 'set launch [get_pins ' + word(start + '/Q') + ']\n'
                    text += 'set capture [get_pins ' + word(target + '/D') + ']\n'
                    text += 'if {[llength $launch]!=1 || [llength $capture]!=1} {error "critical pin identity differs"}\n'
                    text += 'report_checks -from $launch -to $capture -path_delay ' + delay + ' -group_path_count 1 -endpoint_path_count 1 -format full_clock_expanded -digits 9\n'
                    text += 'puts OPENPLL_PAIR_' + str(index) + '_' + delay + '_END\n'
            text += 'exit\n'
            script = directory / 'paths.tcl'
            script.write_text(text)
            pins[str(script)] = sha(script)
            save(output / 'inputs.json', dict(input_sha256=pins, pairs=pairs, CPU=28, memory_GiB=4, actual_frequency_range_qualified=False, release_ready=False))
            save(output / 'status.json', dict(state='measuring_retained_critical_path_pairs', corner=corner, release_ready=False))
            os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', GOMAXPROCS='1')
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            log = directory / 'native.log'
            with lease(1, 4, deadline):
                execute([OPENROAD, '-no_init', '-exit', script], log, deadline, 4)
            native = log.read_text()
            if re.search(r'\[ERROR|Error:|STA-(1648|1650)', native):
                raise ValueError('native query or annotation failed')
            for index, (start, target, kind) in enumerate(pairs):
                for delay in ['min', 'max']:
                    begin = 'OPENPLL_PAIR_' + str(index) + '_' + delay + '_BEGIN'
                    end = 'OPENPLL_PAIR_' + str(index) + '_' + delay + '_END'
                    if native.count(begin) != 1 or native.count(end) != 1:
                        raise ValueError('complete unique path query markers required')
                    row = result(native.split(begin)[1].split(end)[0], start, target, delay)
                    rows.append(dict(corner=corner, classification=kind, **row))
            artifacts[str(log)] = sha(log)
            verify(pins)
        if len(rows) != 30:
            raise ValueError('all thirty paired checks required')
        detail = output / 'paths.json'
        save(detail, rows)
        artifacts[str(detail)] = sha(detail)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts, measured_path_checks=len(rows), new_candidate_route_and_wire_RC_used=True,logical_equivalence_verified=False,historical_internal_cell_views_used=True,full_clock_paths_reported=True, parent_loading_changed_in_this_query=False, timing_exceptions_added=False, actual_frequency_range_qualified=False, cell_models_qualified=False, physical_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='paired_critical_path_diagnostics_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
