"""Inventory physical domains and an oscillator/parent-cell cone.

All capacitor endpoints remain inventoried. This prepares a partition contract;
it does not ground remote terminals or supply an unvalidated stimulus model.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from common_v3 import save,sha,verify


def classify(instances,masters):
    by_master={v:k for k,v in masters.items()};roles={};cells={}
    for item in instances:
        identity=item['physical_hierarchy_identity'];name=item['instance']
        if name in roles:raise ValueError('duplicate physical primitive identifier')
        first=identity[0][2][0] if identity else None
        roles[name]=by_master.get(first,'parent')
        cells[name]=json.dumps([identity,item['leaf_master']],separators=(',',':'))
    if set(masters)-set(roles.values()):raise ValueError('a physical macro domain has no primitive coverage')
    return roles,cells


def parent_cone(terminals,roles,cells,fixed,depth=2):
    by_node=defaultdict(set);by_cell=defaultdict(set)
    for name,ns in terminals.items():
        by_cell[cells[name]].add(name)
        for n in set(ns)-set(fixed):by_node[n].add(name)
    core={n for n,r in roles.items() if r=='oscillator'};selected=set(core);layers=[]
    for _ in range(depth):
        frontier={n for name in selected for n in terminals[name] if n not in fixed}
        touched={name for n in frontier for name in by_node[n] if roles[name]=='parent'}
        complete={name for cell in {cells[n] for n in touched} for name in by_cell[cell]}
        new=complete-selected;selected.update(new);layers.append(sorted(new))
    signal_nodes={n for name in selected for n in terminals[name] if n not in fixed}
    cut={n:sorted(by_node[n]-selected) for n in signal_nodes if by_node[n]-selected}
    return selected,layers,cut,signal_nodes


def run(reference,reduced,frame,output):
    receipts=[p/'assessment.json' for p in (reference,reduced,frame)]
    base,r,f=records=[json.loads(p.read_text()) for p in receipts]
    for record in records:verify(record['input_sha256']);verify(record['artifacts'])
    if not r['complete_reduced_fixed_supply_C_passivity_certified'] or not r['all_active_primitive_and_port_alias_cards_unchanged']:
        raise ValueError('passive complete context reduction with unchanged active cards required')
    if base['assembled_candidate_gds_sha256']!=r['assembled_candidate_gds_sha256']:raise ValueError('manufacturing candidate differs')
    node_file=reference/'nodes.json';model=reduced/'context.spice';original=reference/'context.spice'
    paths=[*receipts,node_file,model,original,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    metadata=json.loads(node_file.read_text());roles,cells=classify(metadata['physical_instances'],{k:v['master'] for k,v in f['macro_sources'].items()})
    fixed={metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes'] if n in metadata['original_to_emitted']}|{'0'}
    terminals={};ports=set();source_cards=[];target_cards=[]
    for line in original.open():
        if line.startswith(('Xflat','Rwire')):source_cards.append(line)
    for line in model.open():
        if line.startswith(('Xflat','Rwire')):target_cards.append(line)
        fields=line.split()
        if not fields:continue
        if fields[0].lower()=='.subckt':ports.update(fields[2:])
        if not fields[0].startswith('Xflat'):continue
        positional=[]
        for token in fields[1:]:
            if token.startswith('sky130_fd_pr__'):break
            positional.append(token)
        else:raise ValueError('unresolved flat primitive')
        if fields[0] in terminals:raise ValueError('duplicate model primitive')
        terminals[fields[0]]=positional
    if source_cards!=target_cards or terminals.keys()!=roles.keys():raise ValueError('primitive sidecar and reduced model differ')
    by_node=defaultdict(set)
    for name,ns in terminals.items():
        for n in set(ns)-fixed:by_node[n].add(roles[name])
    for n in ports-fixed:by_node[n].add('top_port')
    selected,layers,cut,cone_nodes=parent_cone(terminals,roles,cells,fixed)
    counts=Counter();remote=set();unknown=set()
    for line in model.open():
        fields=line.split()
        if not fields or not fields[0].startswith('C'):continue
        if len(fields)!=4:raise ValueError('explicit two-terminal capacitance required')
        a,b=fields[1:3];counts['all_capacitors']+=1
        if fields[0].startswith('CkronGuard'):counts['numerical_guards']+=1
        for n in (a,b):
            if n not in fixed and n not in by_node:unknown.add(n)
        if a in fixed or b in fixed:counts['fixed_supply_incident']+=1
        elif by_node[a]!=by_node[b] or len(by_node[a]|by_node[b])>1:counts['interdomain_or_shared_terminal']+=1
        if a in cone_nodes or b in cone_nodes:
            counts['cone_incident']+=1
            remote.update(n for n in (a,b) if n not in cone_nodes and n not in fixed)
    if unknown:raise ValueError('uninventoried dynamic capacitor endpoints: '+repr(sorted(unknown)[:5]))
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    detail=output/'domains.json';save(detail,dict(primitive_roles=roles,physical_cells=cells,
        signal_node_roles={n:sorted(v) for n,v in by_node.items()},oscillator_and_parent_cone=sorted(selected),parent_cell_expansion_layers=layers,
        cone_cut_conductors=cut,cone_remote_capacitor_terminals=sorted(remote),named_top_ports=sorted(ports),fixed_supply_nodes=sorted(fixed)))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        assembled_candidate_gds_sha256=r['assembled_candidate_gds_sha256'],primitive_counts_by_role=dict(Counter(roles.values())),
        all_primitives_and_dynamic_capacitor_terminals_inventoried=True,whole_parent_cell_cone=True,
        cone_primitive_count=len(selected),cone_parent_expansion_layer_counts=list(map(len,layers)),
        cone_cut_signal_conductors=len(cut),cone_remote_capacitor_terminal_count=len(remote),capacitor_counts=dict(counts),
        remote_terminals_grounded=False,domain_deck_emitted=False,interface_stimuli_validated=False,
        loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('reference','reduced','frame','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.reference.resolve(),a.reduced.resolve(),a.frame.resolve(),a.output.resolve())
