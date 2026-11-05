#!/usr/bin/env python3
"""Record exact nominal C equivalence and rejected spatial-clipping controls."""
from datetime import datetime,timezone
from pathlib import Path
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    names=['qualification_progress_042.json','unordered_nominal_capacitance_comparison_001/assessment.json',
        'nominal_wrapper_capacitance_comparison_001/assessment.json',
        'isolated_magic_stock_build_004/assessment.json','isolated_magic_stock_controls_003/assessment.json',
        'magic_cap_clip_source_patch_002/assessment.json','magic_cap_clip_build_002/assessment.json',
        'magic_cap_clip_default_controls_001/assessment.json','magic_cap_clip_window_controls_001/assessment.json',
        'magic_cap_clip_window_controls_001/comparison.json',
        'isolated_magic_stock_build_001/status.json','isolated_magic_stock_build_001/make.log',
        'isolated_magic_stock_controls_001/min_floating_metal_isolated/extract.log',
        'isolated_magic_stock_controls_002/min_floating_metal_isolated/extract.log',
        'magic_cap_clip_build_001/status.json','magic_cap_clip_build_001/make.log']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);canonical=read(paths[1]);wrapper=read(paths[2]);stock=read(paths[4]);default=read(paths[7]);window=read(paths[8]);cases=read(paths[9])
    assert canonical['exact_positive_capacitor_multisets_preserved'] and canonical['exact_parsed_C_matrix_equivalence_proven']
    assert canonical['counts']=={'orig':22512429,'nom':22512429}
    assert len(set(canonical['canonical_multiset_sha256'].values()))==1
    assert wrapper['all_three_wrapper_native_device_sets_identical']
    assert stock['installed_and_isolated_C_devices_feedback_equal'] and stock['native_CAD_runs']==24
    assert default['installed_and_isolated_C_devices_feedback_equal'] and default['native_CAD_runs']==24
    assert window['native_CAD_runs']==24 and not window['initial_C_window_accounting_controls_passed']
    assert all(r['whole_window_matches_native_C_with_print_allowance'] for r in cases)
    failed=[r for r in cases if not r['signed_quadrants_add_to_whole_within_declared_tolerance']]
    assert {r['case'] for r in failed}=={'floating_metal','floating_poly'}
    analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() not in ['Xyce','ngspice'] or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x];analog.append(dict(pid=int(p.name),argv=argv))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    nominal=dict(full_layout_nominal_wrapper_native_and_collection_terminal=True,
        native_devices_each_RC_corner=100462,all_three_wrapper_native_device_sets_identical=True,
        orig_export_special_model_name_differences=8,
        raw_C_order_and_IDs_changed=True,exact_positive_C_multiset_preserved=True,
        exact_parsed_C_matrix_equivalence_proven=True,positive_C_each_view=22512429,
        canonical_C_multiset_sha256=canonical['canonical_multiset_sha256']['orig'],
        floating_nodes_not_grounded_or_discarded=True,
        original_absolute_CAD_deadline_uptime=3136114.566309955,
        physical_RC_enclosure_qualified=False,runtime_model_adopted=False)
    location=dict(upstream_source_commit='fd12c39c37f26a0fe6e04698b1011e31b8bd3229',
        clean_stock_tool_build='isolated_magic_stock_build_004',
        stock_baseline_native_CAD_runs=24,stock_C_MOS_feedback_equal_to_installed_on_controls=True,
        diagnostic_default_native_CAD_runs=24,diagnostic_default_C_MOS_feedback_equal_to_installed_on_controls=True,
        stock_and_default_baseline_RC_corners=['min','nom','max'],physical_baseline_controls=4,
        native_window_CAD_runs=24,covering_windows_match_native_C_for_all4_controls=True,
        tested_quadrant_accounting_RC_corner='nom',quadrant_accounting_failed_controls=['floating_metal','floating_poly'],
        quadrant_accounting_passed_cell_controls=['HS_NAND','HD_narrow_FF'],
        declared_absolute_comparison_tolerance_ff='0.0001',declared_relative_comparison_tolerance='1e-9',
        floating_metal_SIG_ground_delta_ff=failed[0]['quadrant_sum_differences'][0]['delta_ff'],
        case_comparisons=cases,
        signed_negative_ground_fields_before_output_clamp_retained=True,
        rectangle_clipping_rejected_for_DCO_or_full_layout_C_placement=True,
        clipping_method_adopted=False,full_geometry_contribution_trace_still_required=True,
        installed_extractor_replaced=False,golden_Xyce_backend_changed=False,
        source_control_agreement_proves_full_layout_binary_equivalence=False,
        spatial_C_geometry_or_transient_error_enclosure_qualified=False)
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='exact_nominal_C_equivalence_proven_and_nonadditive_clipping_method_rejected_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        nominal_wrapper_model_work=nominal,C_localization_method_work=location,
        native_analog_jobs=analog,native_analog_count=len(analog),
        next_actions=[
            'Trace contributions from unchanged full geometry, retaining spatial support, signed shielding and clamp adjustments; validate aggregation before DCO use',
            'Do not use the rejected rectangular clipping decomposition for physical C placement',
            'Qualify wire/device/junction spatial RC and transient-error bounds before further long native DCO sweeps',
            'Obtain fresh qualified100/250/300/400 range/calibration evidence; old model brackets cannot choose a physical variant',
            'Complete nominal15PVT timing/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete material/RC enclosure, supply/noise, physical power/jitter/area and integration release gates'])
    snapshot=BASE/'qualification_progress_043.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_nominal_wrapper_model_work']=nominal
    data['active_400mhz_C_localization_method_work']=location
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress043: exact22,512,429-record nominal C equivalence proven; stock/default controls agree; native clipping rejected on floating fill. Physical RC and release qualification remain open.')


if __name__=='__main__':main()
