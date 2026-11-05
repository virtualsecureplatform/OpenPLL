"""Join both native parameter exports to exact spatial terminals without selecting physics."""
import argparse
from array import array
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from common import save,sha
from resources import identity,lease


def parameters(tokens):
    result={}
    for token in tokens:
        if '=' not in token:raise ValueError('native parameter assignment required')
        key,value=token.split('=',1)
        if not key or not value or key in result:raise ValueError('unique native parameter required')
        result[key]=value
    return result


def bind(before,after,geometry,nodes):
    model=geometry['model'];terminals={r[0]:r for r in geometry['terminals']}
    if len(terminals)!=len(geometry['terminals']):raise ValueError('duplicate terminal enum')
    enums=set(terminals)
    if enums=={1,2,3,4}:order=[3,1,2,4]
    elif enums=={1,2}:order=[2,1]
    elif enums=={2,3}:order=[2,3]
    else:raise ValueError('unsupported native terminal set')
    if before[0]!=after[0] or before.count(model)!=1 or after.count(model)!=1:raise ValueError('native instance/model identity')
    position=1+len(order)
    if before.index(model)!=position or after.index(model)!=position:raise ValueError('native card model/terminal arity')
    bindings=[]
    for i,enum in enumerate(order,1):
        _,private,voltage,printed=terminals[enum]
        if private not in nodes:raise ValueError('native terminal private node absent')
        node=nodes[private]
        if (node['global_voltage_id'],node['printed_name'])!=(voltage,printed):raise ValueError('geometry/core node binding mismatch')
        if after[i]!=printed or before[i]!=node['original_conductor']:raise ValueError('pre/post terminal conductor identity mismatch')
        bindings.append(dict(native_terminal_enum=enum,private_id=private,original_voltage_id=voltage,
             pre_R_node_name=before[i],post_R_node_name=after[i],original_conductor=node['original_conductor']))
    pre=parameters(before[position+1:]);post=parameters(after[position+1:])
    differences={k:[pre.get(k),post.get(k)] for k in sorted(pre.keys()|post.keys()) if pre.get(k)!=post.get(k)}
    return order,bindings,pre,post,differences


def read_map(path):
    with path.open('rb') as stream:
        if stream.read(8)!=b'CNETDOF1':raise ValueError('native voltage map format')
        count,targets=struct.unpack('<QQ',stream.read(16));values=array('I')
        if values.itemsize!=4:raise ValueError('native uint32 transport')
        values.fromfile(stream,count)
        if stream.read(1):raise ValueError('map trailing bytes')
    if sys.byteorder!='little':values.byteswap()
    return values,targets


def controls():
    count=0
    for model,order in (('mos',[3,1,2,4]),('diode',[2,1]),('resistor',[2,3])):
        geom=dict(model=model,terminals=[[t,f'p{t}',100+t,f'n{t}'] for t in sorted(order)])
        nodes={f'p{t}':dict(global_voltage_id=100+t,printed_name=f'n{t}',original_conductor=f'old{t}') for t in order}
        before=['X0',*[f'old{t}' for t in order],model,'w=1'];after=['X0',*[f'n{t}' for t in order],model,'w=1']
        actual=bind(before,after,geom,nodes)
        if actual[0]!=order or actual[-1]:raise ValueError('native terminal sequence control')
        changed=after[:-1]+['w=2'];difference=bind(before,changed,geom,nodes)[-1]
        if difference!={'w':['1','2']}:raise ValueError('parameter discrepancy preservation control')
        for pre,post in (([before[0],'wrong',*before[2:]],after),(before,[after[0],'wrong',*after[2:]]),(before,after+['w=3'])):
            try:bind(pre,post,geom,nodes)
            except ValueError:count+=1
            else:raise ValueError('invalid card provenance accepted')
    return count


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve();domain=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/assessment.json')
    delta=base/'startup_timing_native_device_parameter_delta_001/assessment.json';geometry_proof=base/'startup_timing_final_device_basis_audit_001/assessment.json';core=base/'startup_timing_final_native_R_core_002/assessment.json'
    zero=base/'startup_timing_zero_R_voltage_map_002/assessment.json';components=base/'startup_timing_G_components_001/assessment.json'
    proofs=[domain,delta,geometry_proof,core,zero,components];dom,change,geometry_checked,core_checked,z,g=[json.loads(p.read_text()) for p in proofs]
    cards=delta.parent/'native_device_cards.jsonl';difference_ledger=delta.parent/'parameter_differences.jsonl';geometry=geometry_proof.parent/'native_device_terminal_join.jsonl'
    nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl');trace=domain.parent/'trace/SPICE_devices.log';zero_map=zero.parent/'voltage_map.bin';component_map=components.parent/'constrained_voltage_conductors.bin'
    paths=[*proofs,cards,difference_ledger,geometry,nodes,trace,zero_map,component_map,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,runtime_model_eligible=False,release_qualified=False,**more))
    status('waiting_for_one_shared_CPU_slot')
    try:
        with lease(1,4,deadline):
            pins={str(p):sha(p) for p in paths}
            for proof,path in ((change,cards),(change,difference_ledger),(geometry_checked,geometry),(core_checked,nodes),(dom,trace),(z,zero_map),(g,component_map)):
                if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('native provenance artifact changed')
            for name in ('pre_resistance.spice','retained_rc.spice'):
                path=str(domain.parent/'trace'/name)
                if change['input_sha256'][path]!=dom['artifacts'][path]:raise ValueError('paired card cache/extraction lineage differs')
            if g['input_sha256'][str(zero)]!=pins[str(zero)]:raise ValueError('native G voltage map lineage differs')
            negative=controls();expected_changes={r['instance']:r for r in map(json.loads,difference_ledger.read_text().splitlines())}
            physical={};wanted=set()
            with geometry.open() as stream:
                for line in stream:
                    r=json.loads(line);key=(r['model'],*r['point_internal'])
                    if key in physical:raise ValueError('unique native physical model/location required')
                    physical[key]=r;wanted.update(t[1] for t in r['terminals'])
            core_nodes={}
            with nodes.open() as stream:
                for n,line in enumerate(stream):
                    if n%10000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native node join deadline')
                    r=json.loads(line)
                    if r['private_id'] in wanted:
                        if r['private_id'] in core_nodes:raise ValueError('unique native core private node')
                        core_nodes[r['private_id']]={k:r[k] for k in ('global_voltage_id','printed_name','original_conductor')}
            if set(core_nodes)!=wanted:raise ValueError('all native terminal private nodes must resolve')
            phases=[{}]
            with trace.open() as stream:
                for line in stream:
                    m=re.fullmatch(r'DEVICE (X\d+) "([^"]+)" (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)\n',line)
                    if not m:raise ValueError('native geometry trace format')
                    name,model,*numbers=m.groups()
                    if name in phases[-1]:
                        if name!='X0' or len(phases)!=1:raise ValueError('unique native export phases')
                        phases.append({})
                    phases[-1][name]=(model,*map(int,numbers))
            if len(phases)!=2 or phases[0]!=phases[1]:raise ValueError('pre/post native device geometry differs')
            remap,voltage_count=read_map(zero_map);nets,conductor_count=read_map(component_map)
            if voltage_count!=len(nets):raise ValueError('constrained native map dimension')
            status('joining_all_native_cards_to_spatial_terminals');seen_names=set();seen_geometry=set();observed_changes={};terminals=0;ledger=output/'native_device_provenance.jsonl'
            with cards.open() as source,ledger.open('x') as target:
                for line in source:
                    if len(seen_names)%1000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native provenance join deadline')
                    name,before,after=json.loads(line)
                    if name in seen_names or name not in phases[1] or name!=before[0] or name!=after[0]:raise ValueError('unique complete native card instance identity')
                    seen_names.add(name);location=phases[1][name];key=location[:3]
                    if key not in physical or key in seen_geometry:raise ValueError('unique complete physical instance join')
                    seen_geometry.add(key);row=physical[key];order,bindings,pre,post,differences=bind(before,after,row,core_nodes)
                    for binding in bindings:
                        voltage=binding['original_voltage_id']
                        if not 0<voltage<len(remap):raise ValueError('original terminal voltage bounds')
                        constrained=remap[voltage]
                        if not 0<constrained<len(nets) or not 0<nets[constrained]<conductor_count:raise ValueError('constrained terminal/component bounds')
                        binding.update(constrained_voltage_id=constrained,original_conductor_id=nets[constrained]);terminals+=1
                    if differences:observed_changes[name]=dict(instance=name,model=key[0],differences=differences)
                    target.write(json.dumps(dict(instance=name,model=key[0],point_internal=list(key[1:]),native_trace_geometry=list(location[1:]),
                        native_device_pointer=row['native_device_pointer'],native_terminal_order=order,terminal_bindings=bindings,
                        pre_R_card=before,post_R_card=after,pre_R_parameters=pre,post_R_parameters=post,
                        unresolved_parameter_differences=differences,physical_parameter_set_selected=False))+'\n')
            if seen_names!=phases[1].keys() or seen_geometry!=physical.keys() or len(seen_names)!=change['native_devices'] or terminals!=geometry_checked['native_exported_terminal_bindings']:raise ValueError('complete all-device/all-terminal join required')
            if observed_changes!=expected_changes:raise ValueError('parameter discrepancies differ from retained failure audit')
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('native provenance source changed during join')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(ledger):sha(ledger)},
                 all_native_card_parameter_and_terminal_provenance_join_complete=True,native_devices=len(seen_names),native_terminal_bindings=terminals,native_geometry_export_phases=2,
                 both_pre_R_original_conductors_and_post_R_private_nodes_checked=True,unresolved_parameter_devices=len(observed_changes),unresolved_parameter_differences=observed_changes,
                 all_parameter_discrepancies_explicitly_retained=True,negative_controls_rejected=negative,
                 native_SPICE_device_parameter_and_terminal_join_verified=False,physical_parameter_set_selected=False,
                 finite_R_substrate_target_assignment_qualified=False,physical_device_binding_qualified=False,
                 final_projection_node_maps_reconciled=False,runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False))
            status('complete_native_device_provenance_join_retained',devices=len(seen_names),unresolved_parameter_devices=len(observed_changes))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
