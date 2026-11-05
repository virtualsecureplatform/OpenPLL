"""Plan characterized sizing and measured data-hold repairs without RTL exceptions."""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify


def run(route,electrical,endpoints,inventory,obligations,views,output):
    folders=(route,electrical,endpoints,inventory,obligations,views)
    receipts=[p/'assessment.json' for p in folders]
    records=[json.loads(path.read_text()) for path in receipts]
    for record in records:verify(record['input_sha256']);verify(record['artifacts'])
    r,e,h,i,o,v=records
    graph=inventory/'routed.json';violations=electrical/'violations.json'
    paths=endpoints/'paths.json';chains=obligations/'obligations.json'
    module=json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells={name.lstrip('\\'):cell for name,cell in module['cells'].items()}
    libraries=[views/f'{c}_{edge}.lib' for c in ('tt','ff','ss','sf','fs') for edge in ('early','late')]
    available=[set(re.findall(r'cell \(([^)]+)\)',path.read_text())) for path in libraries]
    synchronizers=json.loads(chains.read_text())['synchronizers']
    if len(synchronizers)!=13:raise ValueError('thirteen current synchronizers required')
    first={chain['stages'][0]['routed_cell'].lstrip('\\') for chain in synchronizers}
    intentional=[chain['stages'][0]['routed_cell'].lstrip('\\') for chain in synchronizers
                 if chain['id']=='gen_feedback_tracking.release_pipe']
    if len(intentional)!=1:raise ValueError('explicit reviewed fine capture aperture required')
    sizes={}
    for row in json.loads(violations.read_text()):
        if row['slew_ns']<=row['limit_ns'] or len(row['drivers'])!=1:
            raise ValueError('measured single-driver electrical nonpass required')
        driver=row['drivers'][0];name=driver['cell'];old=driver['master']
        if cells[name]['type']!=old or name in first:raise ValueError('driver differs or first-stage type would change')
        family,strength=old.rsplit('_',1);new=family+'_'+str(2*int(strength))
        if not all(new in masters for masters in available):raise ValueError('replacement lacks characterized views')
        sizes[name]=dict(action='resize',capture_cell=name,capture_master=old,replacement_master=new)
    short=[]
    for path in json.loads(paths.read_text())['failing_endpoint_paths']:
        if path['endpoint']==intentional[0]:continue
        name=path['endpoint'];cell=cells[name]
        if (path['kind']!='min' or not path['slack_ns']<0 or name in first
                or not cell['type'].startswith('sky130_fd_sc_hs__dfrtp_')
                or cell['port_directions'].get('D')!='input'):
            raise ValueError('ordinary measured D-pin hold target required')
        short.append(dict(capture_cell=name,capture_master=cell['type'],capture_pin='D',buffers=1,
            observed_slack_ns=path['slack_ns'],launch_cell=path['startpoint']))
    if len(sizes)!=7 or len(short)!=6:raise ValueError('reviewed seven-driver/six-data sensitivity set differs')
    if 'prototype_observed_load_hold_' in graph.read_text():raise ValueError('fresh buffer namespace required')
    inputs={str(path):sha(path) for path in (*receipts,graph,violations,paths,chains,*libraries,
             route/'route.odb',Path(__file__).resolve())}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=inputs,route_sha256=sha(route/'route.odb'),
        targets=[sizes[name] for name in sorted(sizes)],branches=[],short_data_targets=short,
        all_first_stage_synchronizer_masters_preserved=True,all_replacements_have_native_early_late_tables=True,
        RTL_and_timing_exceptions_unchanged=True,known_load_sensitivity_robustness_repair=True,
        not_a_nominal_hardware_failure_claim=True,physical_candidate_selected=False,release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('route','electrical','endpoints','inventory','obligations','views','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('route','electrical','endpoints','inventory','obligations','views','output')))
