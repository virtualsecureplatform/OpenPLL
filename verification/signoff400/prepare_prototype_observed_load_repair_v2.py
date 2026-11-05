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
    # Classify endpoint pins using native path reports before choosing an ECO.
    native_log=(endpoints/'inventory.log').read_text()
    reset_driver='$auto$ff.cc:337:slice$17896'
    reset_cell=cells[reset_driver]
    reset_bit=reset_cell['connections']['Q'][0]
    reset_sinks=[]
    for name,cell in cells.items():
        for pin,bits in cell['connections'].items():
            if bits==[reset_bit] and cell['port_directions'].get(pin)=='input':
                if pin!='RESET_B' and (name,pin,cell['type']) not in {
                        ('$abc$73649$auto$blifparse.cc:397:parse_blif$73653','A','sky130_fd_sc_hs__clkinv_1'),
                        ('place112','A','sky130_fd_sc_hs__clkbuf_2')}:
                    raise ValueError('reset branch has an unexpected receiver')
                reset_sinks.append(dict(cell=name,pin=pin,master=cell['type']))
    if len(reset_sinks)!=20 or sum(s['pin']=='RESET_B' for s in reset_sinks)!=18:
        raise ValueError('reviewed 18 reset and two logic receivers differ')
    short=[];removal=[]
    for path in json.loads(paths.read_text())['failing_endpoint_paths']:
        if path['endpoint']==intentional[0]:continue
        name=path['endpoint'];cell=cells[name]
        if path['startpoint']==reset_driver:
            blocks=[block for block in native_log.split('Startpoint: ')[1:]
                    if block.startswith(reset_driver+'\n') and 'Endpoint: '+name+'\n' in block]
            if not blocks or not all('removal check' in block and name+'/RESET_B' in block for block in blocks):
                raise ValueError('reset removal target lacks explicit pin evidence')
            if name not in {sink['cell'] for sink in reset_sinks}:raise ValueError('removal receiver not on proved reset net')
            removal.append(name);continue
        if name+'/D ' not in native_log:raise ValueError('ordinary hold lacks D-pin evidence')
        if (path['kind']!='min' or not path['slack_ns']<0 or name in first
                or not cell['type'].startswith('sky130_fd_sc_hs__dfrtp_')
                or cell['port_directions'].get('D')!='input'):
            raise ValueError('ordinary measured D-pin hold target required')
        short.append(dict(capture_cell=name,capture_master=cell['type'],capture_pin='D',buffers=1,
            observed_slack_ns=path['slack_ns'],launch_cell=path['startpoint']))
    if len(sizes)!=2 or len(short)!=1 or len(removal)!=17:raise ValueError('reviewed two-driver/one-data/seventeen-removal set differs')
    if 'prototype_observed_load_followup_hold_' in graph.read_text() or 'prototype_observed_load_followup_branch_' in graph.read_text():raise ValueError('fresh buffer namespace required')
    inputs={str(path):sha(path) for path in (*receipts,graph,violations,paths,chains,*libraries,
             route/'route.odb',endpoints/'inventory.log',Path(__file__).resolve())}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=inputs,route_sha256=sha(route/'route.odb'),
        targets=[sizes[name] for name in sorted(sizes)],branches=[dict(driver=dict(cell=reset_driver,pin='Q',master=reset_cell['type']),sinks=reset_sinks,max_sinks_per_buffer=8,buffer_master='sky130_fd_sc_hs__clkbuf_2')],short_data_targets=short,measured_reset_removal_endpoints=removal,
        all_first_stage_synchronizer_masters_preserved=True,all_replacements_have_native_early_late_tables=True,
        RTL_and_timing_exceptions_unchanged=True,known_load_sensitivity_robustness_repair=True,
        not_a_nominal_hardware_failure_claim=True,physical_candidate_selected=False,release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('route','electrical','endpoints','inventory','obligations','views','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('route','electrical','endpoints','inventory','obligations','views','output')))
