#!/usr/bin/env python3
"""Record the final bounded stock ordering/fill comparison and preserved transients."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    inputs=[Path(__file__).resolve(),owner,base/'qualification_progress_067.json']
    def proof(folder):
        path=base/folder/'assessment.json'
        data=json.loads(path.read_text())
        for name,value in data.get('artifacts',{}).items():assert digest(Path(name))==value,name
        inputs.append(path)
        return data
    exported=proof('DCO_domain_candidate_nom_substrate_output_001')
    assert exported['native_substrate_output_G_convention_experiment']
    assert exported['signed_matrix_branch_realization_readback_passed']
    assert exported['source_original_substrate_G_operators_omitted']==1113704
    fast=proof('DCO_fast_internal_R_node_analysis_001')
    assert fast['candidate_nonterminal_degree1_or2_states']==61527
    assert not fast['independent_state_or_network_changed']
    inventory=proof('native_linear_solver_build_inventory_001')
    assert inventory['build_type']=='Release' and not inventory['engine_or_library_modified']
    comparisons={}
    for name in ['DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_AZTECOO_ILUT_001',
                 'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_AZTECOO_ILUT_no_filter_001',
                 'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_AZTECOO_RILUK1_001',
                 'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_AZTECOO_RILUK2_AMD_001']:
        folder=base/name
        status=json.loads((folder/'status.json').read_text())
        comparisons[name]=status
        assert status['state'] in ['native_seeded_DC_nonpass','performance_budget_inconclusive']
        inputs.append(folder/'input_manifest.json')
        if (folder/'assessment.json').exists():inputs.append(folder/'assessment.json')
        for extra in ['configuration_crash_analysis.json','preconditioner_failure_analysis.json','bounded_nonconvergence_analysis.json']:
            if (folder/extra).exists():inputs.append(folder/extra)
    live=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce','ngspice','magicdnull']:
                row=process(int(p.name))
                if row['live']:live.append(row)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(live)<=4
    transients={}
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001','DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        status=json.loads((base/name/'status.json').read_text())
        wave=base/name/'point.cir.prn'
        lines=wave.read_text().splitlines() if wave.exists() else []
        rows=[s.split() for s in lines[1:] if len(s.split())==4]
        transients[name]=dict(status=status,samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None)
        inputs.append(base/name/'input_manifest.json')
    for name,value in {
        'verification/release_requirements_400mhz.json':'02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json':'2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name)==value
        inputs.append(root/name)
    inputs.extend(Path(__file__).with_name(n) for n in ['run_DCO_seeded_C_free_DC_AZTECOO.py',
        'run_DCO_seeded_C_free_DC_AZTECOO_v2.py','run_DCO_seeded_C_free_DC_AZTECOO_v3.py',
        'run_DCO_seeded_C_free_DC_AZTECOO_v4.py',
        'export_DCO_domain_candidate_v2.py','analyze_DCO_fast_internal_R_nodes.py'])
    throughput=dict(corrected_nominal_diagnostic_export=str((base/'DCO_domain_candidate_nom_substrate_output_001').relative_to(root)),
        corrected_nominal_C_scalar_branches=exported['capacitor_branches'],
        stock_build_inventory={k:v for k,v in inventory.items() if k!='input_sha256'},
        bounded_stock_iterative_comparisons=comparisons,
        no_iterative_configuration_qualified_or_adopted=True,
        candidate_nonterminal_degree1_or2_states=fast['candidate_nonterminal_degree1_or2_states'],
        maximum_internal_RC_comparison_bound_s=fast['maximum_internal_time_constant_comparison_bound_s'],
        conservative_fast_subset_counts=fast['conservative_fast_subset_counts_by_time_constant_s'],
        all_device_and_boundary_vertices_retained_in_analysis=fast['retained_device_and_point_vertices'],
        model_state_removed=False,condensation_or_oscillator_frequency_error_qualified=False,
        active_native_transients=transients,original_deadline_uptime=deadline,budget_restarted=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False)
    previous=json.loads((base/'qualification_progress_067.json').read_text())
    followup=previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live,native_points=transients,active_check_statuses=transients,
        throughput_followup=throughput)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='corrected_nominal_export_ready_stock_iterative_controls_failed_or_inconclusive_fast_internal_state_bounds_measured_native_transients_live',
        restored_self_C_operator_followup=followup,throughput_followup=throughput,
        evidence_sha256={str(p.relative_to(root)):digest(p) for p in inputs},
        active_distributed_RC_followups=[],native_analog_jobs=live,native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Finish the existing native ideal-wire transient reference and preserved full-R transient under the original deadline; ideal-wire results do not qualify finite-R release frequency',
            'Use the measured fast-internal-state bounds to design and validate any passive DC-exact condensation before adopting a reduced native model; retain every MOS/device and physical point interface',
            'Qualify substrate-return convention and dynamic/spatial/numerical errors for the corrected nominal/min/max candidates without restarting identical native cases',
            'Complete all frozen four-mode nominal1.8V/15PVT calibration, timing, reset/CDC, wholePLL, physical and reproducibility gates'])
    snapshot=base/'qualification_progress_068.json';assert not snapshot.exists();save(snapshot,previous)
    overview=root/'build/timing450/implementation_assessment.json';state=json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,active_400mhz_throughput_followup=throughput,
        active_400mhz_distributed_RC_followups=[],release_qualified=False,selected=False,timing_closure_complete=False)
    state['active_400mhz_distributed_RC_check'].update(native_analog_jobs=len(live),
        state='corrected_nominal_export_ready_iterative_comparisons_unqualified_fast_state_bounds_measured_transients_live')
    save(overview,state)
    print('Progress068: final stock iterative comparison also inconclusive at180s; no solver/model reduction adopted; native transients tracked.')


if __name__=='__main__':main()
