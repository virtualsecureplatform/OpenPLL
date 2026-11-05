#!/usr/bin/env python3
"""Record exact native R export reconciliation without qualifying its aliases."""
from datetime import datetime, timezone
from pathlib import Path
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    previous = BASE/'qualification_progress_049.json'
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < read(owner)['deadline_uptime']
    receipt = BASE/'DCO_R_export_alias_audit_002/assessment.json'
    audit = verify(receipt)
    assert audit['all_exported_and_omitted_branches_reconciled']
    assert audit['native_reader_conversion_reproduces_every_exported_R_value_exactly']
    assert sum(audit['omitted_branch_classification'].values()) == 1942
    assert audit['omitted_branch_classification'].get('same_native_pointer', 0) == 0
    engines = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            if name not in ['Xyce', 'ngspice', 'magicdnull']:
                continue
            result = process(int(p.name))
            if result['live']:
                engines.append(dict(kind=name, **result))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not engines, engines
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(receipt=str(receipt.relative_to(ROOT)),
        native_R_branches=audit['native_resistor_records'], SPICE_R_branches=audit['exported_resistors'],
        omitted_branch_classification=audit['omitted_branch_classification'],
        branch_counts_and_exporter_value_conversion_completely_explained=True,
        omitted_branches_connect_distinct_native_voltage_node_pointers=True,
        native_reader_bias_ohm=audit['legacy_reader_additive_bias_ohm'],
        exported_values_differing_from_native_printed_ohms=audit['exported_values_differing_from_native_printed_ohms'],
        exact_native_reader_conversion=audit['reader_expression'],
        physical_alias_voltage_equivalence_qualified=False, native_R_values_bias_free=False,
        replacement_runtime_model_eligible=False, native_CAD_or_analog_runs_added=0)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, receipt, requirements, plan]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='R_export_branch_and_value_conversion_reconciled_distinct_voltage_aliases_unqualified',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        retained_R_mesh_export_reconciliation=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    mapping = dict(progress['distributed_RC_geometry_mapping'])
    mapping['native_geometry_to_SPICE_branch_and_value_conversion_reconciled'] = True
    mapping['native_geometry_to_SPICE_alias_or_omitted_branch_reconciliation_qualified'] = False
    mapping['physical_voltage_equivalence_of_omitted_branches_qualified'] = False
    progress['distributed_RC_geometry_mapping'] = mapping
    progress['next_actions'] = [
        'Capture MOS/intrinsic-R terminal-to-native-pointer bindings and retain unique voltage identifiers across printed names and original aliases',
        'Preserve raw native R values without the legacy reader additive bias; prove interface, device and physical conductor correspondence',
        'Resolve unrecorded terminal cells, C layer identity, local junction/intrinsic-resistor charge and supply/body boundary assumptions',
        'Qualify R/C spatial convergence and device charge conservation before adopting a runtime model',
        'Complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_050.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_R_export_reconciliation'] = evidence
    current['active_400mhz_distributed_RC_geometry_mapping'] = mapping
    current['active_400mhz_distributed_RC_check']['state'] = 'R_export_reconciliation_terminal_physical_voltage_aliases_unqualified'
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress050: all R branch omissions and value conversions explained; physical alias equivalence and runtime eligibility remain unqualified.')


if __name__ == '__main__':
    main()
