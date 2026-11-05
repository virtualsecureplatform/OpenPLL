"""Compare sampled native resolution with the actual fine-domain interstage budget.

This is an observed-grid engineering margin, not a continuous or FIT guarantee.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify

def run(observed,obligations,endpoint_dirs,output):
    rr=observed/'assessment.json';a=json.loads(rr.read_text());verify(a['artifacts'])
    if a['unresolved_final_rail_cases'] or set(a['observed_maximum_resolution_ns_by_corner'])!={'tt','ff','ss','sf','fs'}:raise ValueError('complete resolved five-corner observation grid required')
    ore=obligations/'assessment.json';o=json.loads(ore.read_text());verify(o['artifacts'])
    file=obligations/'obligations.json';chains=json.loads(file.read_text())['synchronizers']
    found=[(i,c) for i,c in enumerate(chains) if c['id']=='gen_feedback_tracking.release_pipe']
    if len(found)!=1:raise ValueError('unique actual fine-domain release chain required')
    index,chain=found[0];source=chain['stages'][0]['routed_cell'].lstrip('\\');destination=chain['stages'][1]['routed_cell'].lstrip('\\')
    inputs={str(p):sha(p) for p in (rr,ore,file,Path(__file__).resolve())};results=[]
    for directory in endpoint_dirs:
        receipt=directory/'assessment.json';record=json.loads(receipt.read_text());verify(record['artifacts'])
        phase=next(Path(n) for n in record['input_sha256'] if n.endswith('/assessment.json') and 'enabled_hold_' in n)
        corner=json.loads(phase.read_text())['native_model_corner']
        log=directory/'inventory.log';section=log.read_text().split(f'INTERSTAGE_{index}_BEGIN',1)[1].split(f'INTERSTAGE_{index}_END',1)[0]
        paths=[x for x in section.split('Startpoint: ')[1:] if 'Path Type: max' in x]
        if len(paths)!=1 or not paths[0].startswith(source+'\n') or 'Endpoint: '+destination not in paths[0]:raise ValueError('matching routed interstage setup path required')
        qrows=[line.split() for line in paths[0].splitlines() if source+'/Q' in line.split()]
        if len(qrows)!=1:raise ValueError('unique measured source clock-to-Q arc required')
        cq=float(qrows[0][0]);detail=directory/'paths.json';data=json.loads(detail.read_text())
        selected=[c for c in data['interstage'] if c['id']==chain['id']]
        if len(selected)!=1:raise ValueError('interstage identity mismatch')
        setup=[p for p in selected[0]['paths'] if p['kind']=='max']
        if len(setup)!=1 or cq<=0:raise ValueError('invalid clock-to-Q or setup budget')
        budget=cq+setup[0]['slack_ns'];tail=a['observed_maximum_resolution_ns_by_corner'][corner]
        results.append(dict(corner=corner,source_clock_to_Q_ns=cq,ordinary_interstage_setup_slack_ns=setup[0]['slack_ns'],available_Q_resolution_time_ns=budget,observed_native_rail_resolution_ns=tail,observed_grid_margin_ns=budget-tail))
        inputs.update({str(p):sha(p) for p in (receipt,phase,log,detail)})
    if sorted(r['corner'] for r in results)!=['ff','fs','sf','ss','tt']:raise ValueError('all five routed corners required')
    verify(inputs);output.mkdir(parents=True,exist_ok=False);report=output/'comparison.json';save(report,results)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(report):sha(report)},first_stage=source,second_stage=destination,chain_id=chain['id'],all_observed_grid_resolution_margins_positive=all(r['observed_grid_margin_ns']>0 for r in results),minimum_observed_grid_margin_ns=min(r['observed_grid_margin_ns'] for r in results),continuous_aperture_or_statistical_tail_bound_proved=False,other_first_stage_resolution_budgets_qualified=False,FIT_qualified=False,physical_CDC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('observed','obligations','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--endpoints',type=Path,action='append',required=True)
    a=p.parse_args();run(a.observed.resolve(),a.obligations.resolve(),[x.resolve() for x in a.endpoints],a.output.resolve())
