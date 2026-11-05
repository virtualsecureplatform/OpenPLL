#!/usr/bin/env python3
"""Record all-corner substrate-G convention checks without adopting the model."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_seeded_C_free_DC import read_bias


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    inputs=[Path(__file__).resolve(),owner,base/'qualification_progress_065.json']
    def proof(folder):
        path=base/folder/'assessment.json'
        data=json.loads(path.read_text())
        for name,expected in data.get('artifacts',{}).items():
            assert digest(Path(name))==expected,name
        inputs.append(path)
        return data
    checks={c:proof(f'DCO_local_C_matrix_{c}_no_substrate_G_checks_001') for c in ['min','nom','max']}
    for check in checks.values():
        assert check['signed_global_passivity_numerical_check_passed']
        assert check['zero_wire_R_collapse_matches_owned_physical_operator_totals']
    matrices={c:proof(f'DCO_local_C_matrix_{c}_no_substrate_G_001') for c in checks}
    assert all(m['counts']['excluded_substrate_G_operators']==1113704 for m in matrices.values())
    accounting=proof('DCO_physical_C_ledger_native_output_001')
    assert accounting['all_three_physical_C_ledgers_match_final_native_extraction']
    kernels=proof('DCO_max_C_mode_kernel_inspection_001')
    assert kernels['selected_kernel_kinds']=={'BLOCKED_FRINGE':15,'FRINGE_HALO':5}
    seeded=proof('DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_001')
    assert seeded['seeded_physical_R_DC_completed']
    bias_paths=[base/f'{name}/operating.ic' for name in ['DCO_domain_nom_tt27_c0_f247_C_free_DC_001',
        'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_001']]
    aa,bb=map(read_bias,bias_paths)
    assert aa.keys()==bb.keys() and len(aa)==174508
    difference=max(abs(aa[n]-bb[n]) for n in aa)
    inputs.extend(bias_paths)
    stop=base/'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_BASKER8_001/stopped_for_performance_comparison.json'
    stopped=json.loads(stop.read_text())
    assert stopped['observed_BASKER_elapsed_s']>stopped['completed_KLU_elapsed_s']
    inputs.append(stop)
    live=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce','ngspice','magicdnull']:
                row=process(int(p.name))
                if row['live']:live.append(row)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(live)<=4
    statuses={}
    for folder in ['DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001',
                   'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001',
                   'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_BASKER8_001']:
        statuses[folder]=json.loads((base/folder/'status.json').read_text())
        assessment=base/folder/'assessment.json'
        if assessment.exists():inputs.append(assessment)
        manifest=base/folder/'input_manifest.json'
        if manifest.exists():inputs.append(manifest)
    for name,expected in {
        'verification/release_requirements_400mhz.json':'02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json':'2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name)==expected
        inputs.append(root/name)
    inputs.extend([Path(__file__).with_name('test_DCO_substrate_G_convention.py'),
        Path(__file__).with_name('check_DCO_C_ledger_native_output.py'),
        Path(__file__).with_name('run_DCO_native_zero_wire_R_point.py')])
    convention=dict(native_substrate_output_writes_zero_C_verified=True,
        both_positive_and_negative_internal_substrate_G_operators_omitted=True,
        omitted_operators_each_corner=1113704,all_explicit_pair_operators_preserved=True,
        numerical_passivity_passed_by_corner={c:checks[c]['signed_global_passivity_numerical_check_passed'] for c in checks},
        zero_R_conservation_passed_by_corner={c:checks[c]['zero_wire_R_collapse_matches_owned_physical_operator_totals'] for c in checks},
        minimum_normalized_eigenvalues_by_corner={c:checks[c]['normalized_minimum_eigenvalues'] for c in checks},
        physical_operator_ledgers_independently_match_final_native_extraction_all_corners=True,
        original_signed_substrate_G_maximum_C_matrix_still_rejected=True,
        full_physical_return_or_finite_R_error_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False)
    previous=json.loads((base/'qualification_progress_065.json').read_text())
    followup=previous['restored_self_C_operator_followup']
    followup.update(substrate_G_output_convention_experiment=convention,
        selected_maximum_negative_ground_kernels=kernels['selected_kernel_kinds'],
        independent_initial_guess_physical_DC_completed=True,
        independent_initial_guess_saved_bias_maximum_difference_V=difference,
        independent_initial_guess_saved_bias_nodes=174508,
        BASKER_performance_comparison_stopped_with_receipt=str(stop.relative_to(root)),
        current_native_engines=live,native_points=statuses,active_check_statuses=statuses)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='all_corner_substrate_G_convention_experiment_passes_native_C_accounting_conservation_and_numerical_passivity_native_transients_live',
        restored_self_C_operator_followup=followup,
        substrate_G_output_convention_experiment=convention,
        active_distributed_RC_followups=[],native_analog_jobs=live,native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        evidence_sha256={str(p.relative_to(root)):digest(p) for p in inputs},
        release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Qualify finite-R substrate return and error bounds for the output-convention correction; numerical passivity and native ideal-C preservation alone do not establish dynamic accuracy',
            'Finish the existing full-domain saved-IC transient and native ideal-wire transient reference under the original owner; never reuse ideal-wire frequency as finite-R release qualification',
            'Use measured sparse-solver costs to improve overnight throughput with stock upstream options and controlled reductions only after explicit error validation',
            'Complete frozen four-mode nominal1.8V/15PVT calibration, timing, reset/CDC, wholePLL, physical and reproducibility gates'])
    snapshot=base/'qualification_progress_066.json'
    assert not snapshot.exists()
    save(snapshot,previous)
    overview=root/'build/timing450/implementation_assessment.json'
    state=json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_substrate_G_output_convention_experiment=convention,
        active_400mhz_distributed_RC_followups=[],release_qualified=False,selected=False,timing_closure_complete=False)
    state['active_400mhz_distributed_RC_check'].update(native_analog_jobs=len(live),
        state='all_corner_substrate_G_output_convention_conservation_passivity_passed_finite_R_accuracy_and_native_transients_open')
    save(overview,state)
    print('Progress066: all3 convention matrices pass; independent final native-C accounting passes; finite-R accuracy and release gates remain open.')


if __name__=='__main__':main()
