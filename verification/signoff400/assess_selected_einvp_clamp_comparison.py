"""Summarize disabled-window clamp proposals and retain their explicit scope limits."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_einvp_window_replay import read,compare


def run(discrete,standard,prepared,inspection,output):
    if output.exists():raise FileExistsError(output)
    dr=discrete/'assessment.json';sr=standard/'assessment.json';ir=inspection;pr=prepared/'assessment.json'
    d,s,physical,p=[json.loads(x.read_text())for x in [dr,sr,ir,pr]]
    for a in [d,s,physical,p]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    if not d['both_proposals_completed'] or not s['both_runs_completed']:raise ValueError('complete runs of all three proposals required')
    files=[dr,sr,ir,pr,prepared/'recorded.csv',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('assess_selected_einvp_window_replay.py')]
    rc,recorded=read(prepared/'recorded.csv');gates={}
    for cell in physical['cells']:
        row={}
        for pin in ['A','TE']:
            nodes=cell['local_to_native_nodes'][pin]
            if len(nodes)!=1:raise ValueError('unique mapped gate driver required')
            i=rc.index(nodes[0]);values=[r[i]for r in recorded];row[pin]=dict(node=nodes[0],range_V=[min(values),max(values)])
        gates[cell['cell']]=row
    configurations=[(kind,discrete/kind,r['device_terminal_ranges_V'])for kind,r in d['proposals'].items()]
    configurations.append(('standard_cell_high_keeper',standard/'prepared',s['device_terminal_ranges_V']))
    results={}
    for name,folder,terminal_ranges in configurations:
        bc,base=read(folder/'base.csv');fc,fine=read(folder/'refined.csv')
        if bc!=fc:raise ValueError('identical proposal vectors required for refinement comparison')
        files += [folder/'base.csv',folder/'refined.csv']
        differences={bc[i]:compare(base,fine,i,i,2.5e-9)['maximum_absolute_error_V']for i in range(1,len(bc))}
        ranges={}
        for cell in physical['cells']:
            node=cell['output_node'];i=[c.lower()for c in fc].index(('v(xcut:'+node+')').lower());values=[r[i]for r in fine if r[0]>=2.5e-9]
            ranges[node]=[min(values),max(values)]
        worst=max((max(abs(v)for v in pair),instance,relation,pair)for instance,relations in terminal_ranges['refined'].items()for relation,pair in relations.items())
        results[name]=dict(refined_output_ranges_V=ranges,maximum_absolute_terminal_difference_V=worst[0],worst_terminal_difference=dict(instance=worst[1],relation=worst[2],range_V=worst[3]),maximum_internal_timestep_difference_V=max(differences.values()),per_vector_timestep_difference_V=differences,assessed_MOS_devices=len(terminal_ranges['refined']),physical_layout_changed=False,new_cell_extracted_parasitics_included=False)
    output.mkdir(parents=True);save(output/'assessment.json',dict(input_sha256={str(f):sha(f)for f in files},proposals=results,recorded_gate_voltage_ranges=gates,window_ns=[200,210],post_initial_cycle_window_ns=[202.5,210],inherited_initial_above_rail_state_not_qualified=True,enabled_behavior_checked=False,enable_transition_contention_checked=False,input_loading_and_frequency_checked=False,new_physical_parasitics_checked=False,all_other_cells_and_corners_checked=False,physical_design_candidate_selected=False,model_validity_ranges_qualified=False,reliability_qualified=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['discrete','standard','prepared','inspection','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.discrete.resolve(),a.standard.resolve(),a.prepared.resolve(),a.inspection.resolve(),a.output.resolve())
