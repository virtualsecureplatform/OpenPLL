#!/usr/bin/env python3
"""Record the validated but performance-rejected general mesh prototype."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    paths = [Path(__file__).resolve(), owner, base / 'qualification_progress_075.json']
    def proof(name):
        path = base / name / 'assessment.json'
        data = json.loads(path.read_text())
        for filename, value in {**data.get('input_sha256', {}), **data.get('artifacts', {})}.items():
            assert digest(Path(filename)) == value, filename
        paths.append(path)
        return data
    controls = proof('passive_RC_mesh_controls_001')
    mesh = proof('DCO_passive_mesh_condensation_nom_1fs_001')
    numerical = proof('DCO_passive_mesh_condensation_nom_1fs_checks_001')
    symbolic = proof('DCO_passive_mesh_condensation_nom_1fs_symbolic_001')
    assert controls['independent_rational_branching_RC_controls_passed']
    assert numerical['signed_global_passivity_numerical_check_passed']
    assert numerical['zero_wire_R_collapse_matches_owned_physical_operator_totals']
    assert mesh['all_protected_vertices_retained'] and mesh['removed_states'] == 44252
    assert symbolic['estimated_flops_ratio'] > 1
    previous = json.loads((base / 'qualification_progress_075.json').read_text())
    work = previous['throughput_followup']
    work['general_mesh_projection_evaluation'] = dict(
        removed_states=mesh['removed_states'], retained_states=mesh['retained_states'],
        all_protected_vertices_retained=True, equivalent_positive_R_branches=mesh['condensed_R_branches'],
        projected_C_nonzeros=mesh['projected_C_nonzeros'],
        rational_DC_and_signed_energy_controls_passed=True,
        numerical_passivity_and_native_zero_R_conservation_passed=True,
        numerical_DC_Schur_relative_error=mesh['equivalent_R_Schur_maximum_relative_difference'],
        passive_block_symbolic_flops_ratio=symbolic['estimated_flops_ratio'],
        passive_block_symbolic_L_nnz_ratio=symbolic['estimated_L_nnz_ratio'],
        nonlinear_device_and_MNA_patterns_included=False,
        rejected_as_performance_fallback=True, actual_native_runtime_checked=False,
        physical_clock_error_qualified=False, active_model_changed=False,
        release_qualified=False, adopted=False)
    cases, live = {}, []
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        text = (folder / 'point.cir.prn').read_text(); lines = text.splitlines()
        if text and not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='general_mesh_projection_passes_rational_DC_native_C_and_numerical_passivity_but_rejected_for_49_percent_worse_passive_symbolic_work',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_076.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress076: general mesh prototype conserves DC/C and passes numerical passivity; rejected for worse symbolic work; native runs unchanged.')


if __name__ == '__main__': main()
