"""Compare matched finite-R and zero-R DCO scope probes without native reruns."""
import argparse,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_DCO_C_scope import sample


def command_identity(command):
    result=list(command)
    for option in ('--rcx-netlist','--build-dir'):
        if result.count(option)!=1:raise ValueError('unique model/output command arguments required')
        result[result.index(option)+1]='<scope-dependent-path>'
    return result


def differences(finite,zero,full):
    if not all(math.isfinite(v) and v>0 for v in (finite,zero,full)):
        raise ValueError('finite positive observed frequencies required')
    return dict(conventional_wire_R_effect_hz=finite-zero,
        conventional_wire_R_effect_ppm=(finite/zero-1)*1e6,
        zero_R_capacitance_scope_shift_hz=full-zero,
        zero_R_capacitance_scope_shift_ppm=(full/zero-1)*1e6,
        additive_scope_corrected_finite_R_estimate_hz=finite+full-zero,
        additive_estimate_is_not_a_measured_full_C_finite_R_result=True)


def run(finite,zero,full,start,stop,output):
    directories={'conventional_finite_R':finite,'conventional_zero_R':zero,'full_C_zero_R':full}
    records={};pins={};identities=[];layouts=[];commands=[]
    for label,directory in directories.items():
        identity,layout,metrics,bound=sample(directory,start,stop)
        identities.append(identity);layouts.append(layout);pins.update(bound);records[label]=metrics
        manifest=json.loads((directory/'input_manifest.json').read_text())
        commands.append(command_identity(manifest['command']))
        expected={'conventional_zero_R':'conventional_zero_wire_R','full_C_zero_R':'full_C_zero_wire_R'}.get(label)
        if expected and manifest.get('scope_control')!=expected:raise ValueError('wrong zero-R scope control')
        if not expected and manifest.get('scope_control'):raise ValueError('finite-R baseline is a scope control')
    if any(i!=identities[0] for i in identities) or any(l!=layouts[0] for l in layouts):
        raise ValueError('same operating point and physical candidate required')
    if any(c!=commands[0] for c in commands):raise ValueError('solver, stimuli, tolerances or worker differ')
    frequency={k:r['average_frequency_hz'] for k,r in records.items()}
    shifts=differences(*(frequency[k] for k in directories))
    for name in ('compare_prototype_DCO_C_scope.py','assess_prototype_native_waveform.py'):
        p=Path(__file__).with_name(name);pins[str(p)]=sha(p)
    pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve());verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'comparison.json'
    save(detail,dict(operating_point=dict(zip(('corner','temperature_c','supply_v','coarse_code','fine_code'),identities[0])),
        candidate_gds_sha256=layouts[0],window_start_ns=start,window_stop_ns=stop,
        average_frequency_hz=frequency,all_cycle_metrics=records,**shifts))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        same_candidate_operating_point_and_native_command_verified=True,
        all_complete_captured_cycles_in_identical_window_assessed=True,native_simulations_started=0,
        cell_local_C_retained_in_scope_controls=True,
        finite_R_and_scope_error_interaction_bounded=False,numerical_uncertainty_included=False,
        parent_loading_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('finite','zero','full','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--start-ns',type=float,default=10);p.add_argument('--stop-ns',type=float,default=40)
    a=p.parse_args();run(a.finite.resolve(),a.zero.resolve(),a.full.resolve(),a.start_ns,a.stop_ns,a.output.resolve())
