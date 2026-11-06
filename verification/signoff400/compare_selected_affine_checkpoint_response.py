"""Compare a certified affine variant with its terminal original native trace.

An original budget prefix can cover the comparison window without completing
its full horizon. Source currents and absolute charges remain out of scope.
"""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from audit_selected_dco_history_inputs import sources
from run_selected_fixed_boundary_fold_control_v2 import nonlinear_text
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from selected_spice_device_conditions import matching


def run(original,folded,certificate,output):
    if output.exists():raise FileExistsError(output)
    c=json.loads(certificate.read_text());verify(c['input_sha256']);verify(c['artifacts']);om=json.loads((original/'manifest.json').read_text());fm=json.loads((folded/'manifest.json').read_text())
    for m in(om,fm):verify(m['input_sha256'])
    if c['input_sha256'].get(str(original/'manifest.json'))!=sha(original/'manifest.json') or fm['original_native_case']!=str(original) or fm['original_native_case_manifest_sha256']!=sha(original/'manifest.json'):raise ValueError('fold must bind the exact original native case')
    if not all(c[k] for k in ('nonlinear_cards_and_subcircuits_unchanged','retained_node_equations_exact_before_serialization','serialized_free_C_passivity_certified')):raise ValueError('certified affine fold required')
    if not fm['affine_fixed_boundary_fold_applied']:raise ValueError('actual native must use the fold')
    for key in('controls','operating_point','observed_roles','native_checkpoint_time_s','simulation_end_s','initialized_private_nodes'):
        if om[key]!=fm[key]:raise ValueError('same physical observations, initialization and operating point required')
    devices=certificate.parent/'devices.spice';fold_sources=certificate.parent/'sources.spice'
    if nonlinear_text((original/'devices.spice').read_text())!=nonlinear_text(devices.read_text()):raise ValueError('nonlinear definitions changed')
    before,after=sources(original/'sources.spice'),sources(fold_sources);removed=set(before)-set(after)
    if set(after)-set(before) or any(before[n]!=after[n] for n in after):raise ValueError('surviving fixed/dynamic source changed')
    if len(removed)!=c['removed_constant_voltage_sources']:raise ValueError('removed source inventory differs')
    for n in removed:
        try:float(before[n][1])
        except ValueError:raise ValueError('dynamic source removal forbidden')
    text=(original/'control.spice').read_text()
    for old,new in ((original/'devices.spice',devices),(original/'sources.spice',fold_sources),(original/'control.raw',folded/'control.raw')):
        if text.count(str(old))!=1:raise ValueError('unique original deck reference required')
        text=text.replace(str(old),str(new))
    if text!=(folded/'control.spice').read_text():raise ValueError('initial conditions, solver or observations changed')
    matching(original/'control.spice',folded/'control.spice');edges=[];outcomes=[];starts=[];paths=[certificate,Path(__file__).resolve(),devices,fold_sources,original/'devices.spice',original/'sources.spice']
    for folder,m in ((original,om),(folded,fm)):
        state=json.loads((folder/'status.json').read_text());normal=state['state']=='saved_state_DCO_diagnostic_complete';budget=state['state']=='stopped_without_qualification' and 'TimeoutError' in state.get('reason','')
        if not (normal or budget) or folder==folded and not normal:raise ValueError('terminal original and normally completed affine horizon required')
        worker=json.loads((folder/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('native remains live')
        rows,info=read_prefix(folder/'control.raw',m['observed_roles'])
        if normal and (info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-m['simulation_end_s'])>1e-18):raise ValueError('normally completed full horizon required')
        e,start=aligned(rows,1,2)
        if start['end_age_ns']<40:raise ValueError('complete 10--40 ns common age required')
        edges.append(e);starts.append(start);outcomes.append(dict(normal_full_horizon_completed=normal,budget_stopped=budget,last_complete_ns=rows[-1][0]*1e9,waveform=info))
        if normal:
            a=json.loads((folder/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts']);paths.append(folder/'assessment.json')
        paths += [folder/n for n in ('manifest.json','status.json','native.process.json','control.raw','control.spice')]
    paths += [Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','audit_selected_dco_history_inputs.py','run_selected_fixed_boundary_fold_control_v2.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','selected_spice_device_conditions.py')]
    pins={str(p):sha(p) for p in paths};verify(pins);save(output,dict(input_sha256=pins,original_outcome=outcomes[0],affine_outcome=outcomes[1],frequency_comparisons=metrics(edges[1],edges[0],40),first_output_rise_difference_ps=(starts[1]['first_oscillator_rise_ns']-starts[0]['first_oscillator_rise_ns'])*1000,actual_nonlinear_sources_IC_and_solver_invariance_checked=True,retained_voltage_affine_equations_certified=True,fixed_source_current_and_absolute_charge_equivalence_claimed=False,scope='One TT fine133 initialized coherent partition; original terminal prefix covers full common-age comparison, affine variant completes its original horizon. No uniform tuning-family error or controlled throughput benchmark.',uniform_model_uncertainty_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('original','folded','certificate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.original.resolve(),a.folded.resolve(),a.certificate.resolve(),a.output.resolve())
