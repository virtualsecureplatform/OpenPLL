#!/usr/bin/env python3
"""Record general fast-node selection with a direct protected-terminal audit."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import numpy as np
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    selected_dir = base / 'DCO_adaptive_fast_internal_R_selection_nom_1fs_002'
    proof_path = selected_dir / 'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['selection_converged'] and proof['selected_nonterminal_states'] == 44252
    for name, value in {**proof['input_sha256'], **proof['artifacts']}.items():
        assert digest(Path(name)) == value, name
    nodes_path = base / 'DCO_local_C_matrix_nom_no_substrate_G_001/nodes.json'
    device_path = base / 'DCO_complete_domain_model_primitives_001/device_connections.json'
    boundary_path = base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    names = json.loads(nodes_path.read_text())
    protected = {node for device in json.loads(device_path.read_text()).values() for node in device['private_terminals']}
    protected.update(row['private_node'] for row in json.loads(boundary_path.read_text()))
    protected.add('_dco_substrate_reference')
    assert len(protected) == 34413
    selection = np.load(selected_dir / 'selected_comparison_bounds.npz')
    indices, bounds = selection['node_indices'], selection['upper_bounds_s']
    assert len(set(indices)) == len(indices) == 44252
    assert not protected.intersection(names[index] for index in indices)
    assert np.isfinite(bounds).all() and max(bounds) <= 1e-15
    previous_path = base / 'qualification_progress_074.json'
    previous = json.loads(previous_path.read_text())
    work = previous['throughput_followup']
    work['general_fast_node_selection'] = dict(directory=str(selected_dir.relative_to(root)),
        selected_internal_vertices=44252, protected_device_and_point_vertices=34413,
        direct_protected_terminal_membership_audit_passed=True,
        maximum_numerical_RC_comparison_bound_s=float(max(bounds)), iterations=len(proof['iterations']),
        physical_state_or_network_changed=False, projection_performed=False,
        projected_pattern_or_performance_checked=False,
        oscillator_frequency_error_qualified=False, release_qualified=False, adopted=False)
    cases, live = {}, []
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        text = (folder / 'point.cir.prn').read_text(); lines = text.splitlines()
        if not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    paths = [Path(__file__).resolve(), owner, previous_path, proof_path, device_path, boundary_path,
        nodes_path, base / 'DCO_all_internal_R_node_analysis_001/assessment.json',
        base / 'DCO_adaptive_fast_internal_R_selection_nom_1fs_001/assessment.json']
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='general_nonterminal_RC_selection_converges_44252_vertices_with_1fs_numerical_comparison_bound_protected_terminal_audit_pass_no_model_change',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_075.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress075:44252 fast internal candidates selected with protected-terminal audit; no model change, native jobs live.')


if __name__ == '__main__':
    main()
