"""Compare original/extended physical partitions over a declared common age window.

A terminal capped prefix may supply the common window, but is never labeled a
normally completed original horizon or a uniform partition uncertainty bound.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from selected_spice_device_conditions import matching


def run(original,larger,audit,output):
    if output.exists():raise FileExistsError(output)
    proof=json.loads(audit.read_text());verify(proof['input_sha256'])
    for key in('original_cards_and_private_voltage_values_preserved','common_boundary_waveforms_and_quiet_voltages_identical','same_solver_and_checkpoint_protocol'):
        if proof.get(key)is not True:raise ValueError('independent physical-partition-only input audit required')
    manifests=[];edges=[];starts=[];outcomes=[];paths=[audit,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','selected_spice_device_conditions.py'))]
    for d in(original,larger):
        manifest=d/'manifest.json'
        if proof['input_sha256'].get(str(manifest))!=sha(manifest):raise ValueError('audit applies to another native partition')
        m=json.loads(manifest.read_text());verify(m['input_sha256']);manifests.append(m)
        status=json.loads((d/'status.json').read_text());normal=status['state']=='saved_state_DCO_diagnostic_complete';budget=status['state']=='stopped_without_qualification'and'TimeoutError'in status.get('reason','')
        if not(normal or budget):raise ValueError('terminal normal completion or explicit budget stop required')
        worker=json.loads((d/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('native partition remains live')
        rows,info=read_prefix(d/'control.raw',m['observed_roles'])
        if normal and(info['incomplete_final_sample_discarded']or abs(rows[-1][0]-m['simulation_end_s'])>1e-18):raise ValueError('normally completed partition must include full horizon')
        e,start=aligned(rows,1,2)
        if start['end_age_ns']<40:raise ValueError('required common 10--40 ns oscillator-age window missing')
        edges.append(e);starts.append(start);outcomes.append(dict(normal_full_horizon_completed=normal,native_budget_stopped=budget,complete_prefix_end_ns=rows[-1][0]*1e9,prefix_info=info))
        paths += [d/n for n in('manifest.json','status.json','native.process.json','control.raw','control.spice')]
        if normal:
            a=json.loads((d/'assessment.json').read_text());verify(a['artifacts']);paths.append(d/'assessment.json')
    for key in('controls','operating_point','native_checkpoint_time_s','simulation_end_s','observed_roles'):
        if manifests[0][key]!=manifests[1][key]:raise ValueError('same operating point, initialization time and observed roles required')
    matching(original/'control.spice',larger/'control.spice');differences=metrics(edges[1],edges[0],40)
    renamed={key:dict(window_after_first_rise_ns=value['window_after_first_rise_ns'],larger_partition=value['candidate'],original_partition=value['full_native'],difference_ppm=value['difference_ppm'])for key,value in differences.items()}
    pins={str(p):sha(p)for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,operating_point=manifests[0]['operating_point'],controls=manifests[0]['controls'],original_outcome=outcomes[0],larger_outcome=outcomes[1],
        required_common_oscillator_age_window_ns=[10,40],full_required_common_window_available=True,frequency_comparisons=renamed,
        first_output_rise_difference_ps=1000*(starts[1]['first_oscillator_rise_ns']-starts[0]['first_oscillator_rise_ns']),
        scope='One measured TT partition extension. Common-age response is available from a terminal prefix; the extended original horizon did not necessarily complete. Both use the same observed physical nodes.',
        uniform_partition_uncertainty_bound_qualified=False,model_family_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('original','larger','audit','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('original','larger','audit','output')))
