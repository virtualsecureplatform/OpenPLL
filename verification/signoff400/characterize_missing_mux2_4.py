"""Fill the repaired digital candidate's missing raw mux2_4 15-PVT grid."""
import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import itertools
import json
import os
from pathlib import Path
import re
import threading
import time
from common import save,sha
from compiled_charge import execute
from resources import identity,lease


def truth(function,values):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Name):return values[n.id]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Invert):return 1-visit(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.BitAnd):return a&b
            if isinstance(n.op,ast.BitOr):return a|b
        raise ValueError('unsupported mux Boolean function')
    return visit(ast.parse(function.replace('!','~'),mode='eval'))


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/timing400/release_001'
    requirements=root/'verification/signoff400/requirements.json'
    route=root/'build/signoff400/startup_corrected_timing_repair_003/route.v'
    route_receipt=route.parent/'assessment.json'
    index=base/'hs_cell_model_index_001/assessment.json';reference=base/'compact_propagation_tt27_001/plan.json'
    data=root/'build/timing450/pdk_src/sky130_fd_sc_hs/cells/mux2/sky130_fd_sc_hs__mux2_4__tt_025C_1v80_ccsnoise.lib.json'
    master='sky130_fd_sc_hs__mux2_4';entry=json.loads(index.read_text())['models'][master];model=Path(entry['model'])
    source_receipt=Path(entry['source_assessment']);image=root/'build/apptainer/openpll-release-modern.sif'
    worker=root/'verification/timing400/run_mux2_4_PVT_case.py';parser=root/'verification/timing400/assess_compact_propagation_campaign.py'
    dependencies=[root/'verification/timing400'/n for n in ('characterize_compact_propagation.py','run_dco_qualification.py')]
    paths=[requirements,route,route_receipt,index,reference,data,model,source_receipt,image,worker,parser,*dependencies,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,wall_limit_s=43200,
         maximum_case_workers=8,internal_native_threads=1,case_address_space_limit_GiB=4,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    status('pinning_current_candidate_and_retained_mux_model')
    pins={str(p):sha(p) for p in paths};spec=json.loads(requirements.read_text())
    if spec['voltages']!=[1.8] or len(spec['corners'])*len(spec['temperatures_c'])!=15:raise ValueError('accepted PVT scope changed')
    if pins[str(model)]!=entry['model_sha256']:raise ValueError('retained extracted mux model changed')
    counts=Counter(re.findall(r'^\s*(sky130_fd_sc_hs__\w+)\s+(?:\\\S+|\w+)\s*\(',route.read_text(),re.M))
    if counts[master]!=4:raise ValueError('expected four repaired candidate mux2_4 instances')
    original=json.loads(reference.read_text());existing={r['master'] for r in original['fixtures']}
    if master in existing:raise ValueError('new measurements must cover a missing master')
    lib=json.loads(data.read_text());cp={k[4:]:v for k,v in lib.items() if k.startswith('pin,') and isinstance(v,dict)}
    inputs=sorted(n for n,v in cp.items() if v.get('direction')=='input');outputs=[n for n,v in cp.items() if v.get('direction')=='output']
    if inputs!=['A0','A1','S'] or outputs!=['X']:raise ValueError('mux interface differs')
    function=cp['X']['function'];maximum=float(cp['X']['max_capacitance'])
    for bits in itertools.product((0,1),repeat=3):
        v=dict(zip(inputs,bits))
        if truth(function,v)!=(v['A1'] if v['S'] else v['A0']):raise ValueError('independent mux truth table')
    ports=entry['ports'];supplies={'VNB':'0','VPB':'VDD','VPWR':'VDD','VGND':'0'}
    if set(ports)!=set(inputs)|{'X'}|set(supplies):raise ValueError('extracted model ports differ')
    fixtures=[]
    for changing in inputs:
        other=[n for n in inputs if n!=changing]
        for bits in itertools.product((0,1),repeat=2):
            side=dict(zip(other,bits));low=truth(function,{**side,changing:0});high=truth(function,{**side,changing:1})
            if low==high:continue
            for ramp,load in itertools.product((20,200,1000/0.6),(0,maximum/4,maximum)):
                fixtures.append(dict(master=master,input=changing,output='X',side_inputs=side,inverted=low>high,full_ramp_ps=ramp,external_load_pf=load,ports=ports))
    if len(fixtures)!=54:raise ValueError('complete sensitization/load/slew grid')
    PDK='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A'
    cases=[]
    for corner,temperature in itertools.product(spec['corners'],spec['temperatures_c']):
        label=f'{corner}_{temperature}';folder=output/label;folder.mkdir()
        lines=[f'* Missing mux2_4 raw propagation: {len(fixtures)} fixtures.',f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',f'.include "{model}"',f'.options device temp={temperature}',
               '.options timeint reltol=1e-5 abstol=1e-10','VSUP VDD 0 1.8'];columns=[]
        for i,case in enumerate(fixtures):
            aliases={**supplies,case['input']:f'IN_{i}','X':f'OUT_{i}',**{p:'VDD' if v else '0' for p,v in case['side_inputs'].items()}}
            lines.extend([f'VIN_{i} IN_{i} 0 PULSE(0 1.8 2n {case["full_ramp_ps"]:.12g}p {case["full_ramp_ps"]:.12g}p 5n 16n)',f'XDUT_{i} '+' '.join(aliases[p] for p in ports)+' '+master])
            if case['external_load_pf']>0:lines.append(f'CLOAD_{i} OUT_{i} 0 {case["external_load_pf"]:.12g}p')
            columns.extend([f'V(IN_{i})',f'V(OUT_{i})'])
        lines.extend(['.tran 2p 34n 0 2p','.print tran '+' '.join(columns),'.end'])
        deck=folder/'batch.cir';deck.write_text('\n'.join(lines)+'\n');plan=folder/'plan.json'
        save(plan,dict(input_sha256={**pins,str(deck):sha(deck)},reference_plan=str(reference),deadline_uptime=deadline,
             fixtures=fixtures,pvt=dict(corner=corner,supply_v=1.8,temperature_c=temperature),physical_timing_qualified=False,release_qualified=False))
        cases.append((label,plan))
    save(output/'plan.json',dict(input_sha256=pins,candidate_cell_counts=dict(counts),previous_raw_combinational_masters=sorted(existing),missing_master=master,
         measured_fixtures_per_PVT=54,independent_truth_rows_checked=8,cases=[dict(label=l,plan=str(p)) for l,p in cases],
         model_scope=entry['model_scope'],interpolation_qualified=False,physical_timing_qualified=False,release_qualified=False))
    lock=threading.Lock();done=[]
    python='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
    def task(case):
        label,plan=case
        with lease(1,4,deadline):
            command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,python,worker,'--plan',plan]
            execute(command,plan.parent/'worker.log',deadline,4)
        receipt=plan.parent/'run_001/assessment.json';a=json.loads(receipt.read_text())
        result=dict(label=label,assessment=str(receipt),assessment_sha256=sha(receipt),passing=a['passing'],strict_output_slew_passing=a['strict_output_slew_passing'],fixtures=a['fixtures'])
        with lock:
            done.append(result);status('native_mux2_4_grid_running',completed_points=len(done),required_points=15);save(output/'case_results.json',done)
        return result
    status('native_mux2_4_grid_running',completed_points=0,required_points=15)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=[future.result() for future in as_completed([pool.submit(task,case) for case in cases])]
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('candidate or characterization input changed')
        save(output/'assessment.json',dict(input_sha256=pins,case_results=results,required_PVT_points=15,completed_raw_PVT_points=len(results),
             all_raw_fixture_events_pass=all(r['passing']==54 and r['strict_output_slew_passing']==54 for r in results),fixtures_per_PVT=54,master=master,
             numerical_domain_enclosure_qualified=False,interpolation_qualified=False,sequential_constraints_qualified=False,
             physical_timing_qualified=False,release_qualified=False))
        status('all_15_raw_mux2_4_PVT_points_terminal',passing_points=sum(r['passing']==54 for r in results))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error),completed_points=len(done));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
