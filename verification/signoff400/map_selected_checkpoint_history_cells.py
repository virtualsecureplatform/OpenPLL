"""Join the measured IC-sensitive context to literal physical load-cell topology."""
import argparse,json,os,time
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from run_selected_checkpoint_IC_swap import initial


def locate(mapping,nodes):
    reverse=defaultdict(list)
    for label,node in mapping.items():reverse[node].append(label)
    result={}
    for node in nodes:
        labels=[x for x in reverse[node]if '/sky130_fd_sc_hd__einvp_1_'in x]
        if len(labels)!=1:raise ValueError('unique e-inverter physical label required for every context node')
        cell,pin=labels[0].rsplit('/',1)
        if pin not in ['Z','a_204_47#','a_276_297#','a_27_47#']:raise ValueError('expected output or internal load-cell node')
        result[node]=dict(cell=cell,local_pin=pin)
    return result


def cards(path):
    calls={};blocks={};current=None;passives=defaultdict(list)
    for line in path.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt'and f[1].startswith('__openpll_literal_leaf_'):
            current=f[1];blocks[current]=[tuple(f)];continue
        if current is not None:
            blocks[current].append(tuple(f))
            if f[0].lower()=='.ends':current=None
        if f[0].startswith('Xflat'):
            if len(f)<4:raise ValueError('complete literal primitive call required')
            calls[f[0]]=f
        if f[0][0].upper()in ['R','C']and len(f)==4:
            for node in f[1:3]:passives[node].append(tuple(f))
    return calls,blocks,passives


def run(factorial,context,target,donor,physical_review,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{23})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1800):
        fp=factorial/'assessment.json';fr=json.loads(fp.read_text());review=json.loads(physical_review.read_text());cm=context/'manifest.json';c=json.loads(cm.read_text())
        for a in [fr,review,c]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
        if not fr['all_four_native_cases_completed_normally']or not fr['exact_complementary_IC_interventions_verified']or not review['selected_artifact_lineage_links_verified']:raise ValueError('verified factorial and selected physical lineage required')
        nodes=fr['context_nodes']
        if len(nodes)!=12 or c['context_nodes']!=nodes or fr['context_size']!=12:raise ValueError('identical measured twelve-node context required')
        np=Path(next(x for x in review['input_sha256']if x.endswith('/nodes.json')));full=Path(next(x for x in review['input_sha256']if x.endswith('/model.spice')))
        metadata=json.loads(np.read_text());mapping=metadata['original_to_emitted'];locations=locate(mapping,nodes)
        own_path=target/'initial_conditions.spice';donor_path=donor/'initial_conditions.spice';hybrid_path=context/'initial_conditions.spice'
        if any(fr['input_sha256'].get(str(p))!=sha(p)for p in [own_path,donor_path,hybrid_path]):raise ValueError('factorial must bind all three actual initial-condition files')
        own,old,hybrid=[initial(p)for p in [own_path,donor_path,hybrid_path]]
        if set(own)!=set(old)or set(own)!=set(hybrid):raise ValueError('same initialized private nodes required')
        if any(hybrid[n]!=(old[n]if n in nodes else own[n])for n in own):raise ValueError('exact measured context intervention required')
        device=target/'devices.spice'
        if c['input_sha256'].get(str(device))!=sha(device):raise ValueError('actual measured context must bind target device cards')
        native_calls,native_blocks,native_passives=cards(full);conditional_calls,conditional_blocks,conditional_passives=cards(device)
        physical=metadata['physical_instances'];byname={r['instance']:r for r in physical};records=[]
        for cell in sorted({r['cell']for r in locations.values()}):
            z=mapping[cell+'/Z'];seeds=[name for name,f in native_calls.items()if z in f[1:5]and name in byname and byname[name]['leaf_master']=='sky130_fd_sc_hd__einvp_1']
            identities={json.dumps(byname[n]['physical_hierarchy_identity'],sort_keys=True)for n in seeds}
            if len(identities)!=1:raise ValueError('unique physical load-cell group required')
            identity=next(iter(identities));group=[r for r in physical if r['leaf_master']=='sky130_fd_sc_hd__einvp_1'and json.dumps(r['physical_hierarchy_identity'],sort_keys=True)==identity]
            if len(group)!=6:raise ValueError('six MOS per physical e-inverter required')
            local=defaultdict(set);names=[]
            for row in group:
                name=row['instance'];names.append(name);f=native_calls[name]
                if len(f)!=6:raise ValueError('literal four-terminal MOS call required')
                if conditional_calls.get(name)!=f or conditional_blocks.get(f[-1])!=native_blocks.get(f[-1]):raise ValueError('same literal physical MOS geometry and connections required in measured partition')
                family,ports,_=row['local_primitive_signature'];leaf=native_blocks[f[-1]]
                if leaf[1][5]!=family:raise ValueError('physical and native primitive families differ')
                for pin,node in zip(ports,f[1:5]):local[pin].add(node)
            if any(len(values)!=1 for values in local.values()):raise ValueError('unique local cell terminal mapping required')
            local={pin:next(iter(values))for pin,values in local.items()}
            outside=[name for name,f in native_calls.items()if z in f[1:5]and name not in names]
            resistors=[f[0]for f in native_passives[z]if f[0][0].upper()=='R']
            records.append(dict(cell=cell,flat_MOS_instances=sorted(names),local_to_native_nodes=local,sensitive_local_pins={node:locations[node]['local_pin']for node in nodes if locations[node]['cell']==cell},outside_cell_primitive_connections_to_Z=outside,explicit_resistors_on_Z=resistors,full_capacitor_cards_on_Z=sum(f[0][0].upper()=='C'for f in native_passives[z]),conditional_capacitor_cards_on_Z=sum(f[0][0].upper()=='C'for f in conditional_passives[z]),initial_voltages_V={pin:dict(node=node,own112=own.get(node),donor111=old.get(node),context111=hybrid.get(node))for pin,node in local.items()}))
        if len(records)!=4:raise ValueError('four physical load cells expected from measured context')
        files=[fp,cm,physical_review,np,full,device,own_path,donor_path,hybrid_path,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('run_selected_checkpoint_IC_swap.py')]
        output.mkdir(parents=True);save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},context_node_locations=locations,cells=records,all_24_MOS_cards_and_wrappers_identical_in_measured_partition=True,all_four_Z_have_no_outside_primitives_or_resistors=all(not r['outside_cell_primitive_connections_to_Z']and not r['explicit_resistors_on_Z']for r in records),factorial_windows=fr['windows'],scope='Physical location and exact partition binding of already measured IC sensitivity. Disabled-state history mechanism and clamp remedy not proved by this join.',hybrid_physical_reachability_assumed=False,clamp_history_remedy_verified=False,full_native_switched_equivalence_qualified=False,model_family_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['factorial','context','target','donor','physical-review','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.factorial.resolve(),a.context.resolve(),a.target.resolve(),a.donor.resolve(),a.physical_review.resolve(),a.output.resolve())
