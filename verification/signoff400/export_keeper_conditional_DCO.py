"""Export a port-complete conditional circuit, with no default boundary voltages."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_DCO_driver_C_cut import capacitance
from native_spice_comments import strip_floating_annotation

RAILS={'VPWR','VGND','VPB','VNB','0'}

def partition(text,selected):
    primitives=[];caps=[];names=set();formal_ports=set();in_header=False
    for raw in text.splitlines():
        line=strip_floating_annotation(raw).strip();f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':
            formal_ports.update(f[2:]);in_header=True;continue
        if f[0]=='+':
            if not in_header:raise ValueError('only header continuation supported')
            formal_ports.update(f[1:]);continue
        if not f[0].startswith('*'):in_header=False
        if f[0][0] not in 'XC':continue
        if f[0] in names:raise ValueError('duplicate card')
        names.add(f[0])
        if f[0][0]=='X':
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
            if not f[j].startswith('sky130_fd_pr__'):raise ValueError('flat native primitive required')
            primitives.append((f[0],set(f[1:j]),line))
        else:
            if len(f)!=4:raise ValueError('literal capacitor required')
            value=capacitance(f[3])
            if value<0:raise ValueError('nonnegative capacitance required')
            if value:caps.append((f[0],set(f[1:3]),line))
    chosen=[r for r in primitives if r[0] in selected]
    if {r[0] for r in chosen}!=selected:raise ValueError('selected primitive missing')
    nodes=set().union(*(r[1] for r in chosen));nonrail=nodes-RAILS
    kept=[r for r in caps if r[1]&nonrail or r[1]<=RAILS]
    omitted_primitives=[r for r in primitives if r[0] not in selected]
    exterior_primitive_nodes=set().union(*(r[1] for r in omitted_primitives)) if omitted_primitives else set()
    cap_nodes=set().union(*(r[1] for r in kept)) if kept else set()
    boundary=(nodes&exterior_primitive_nodes)|(cap_nodes-nodes)|(nodes&RAILS)|(cap_nodes&RAILS)
    boundary|=(nodes|cap_nodes)&formal_ports
    boundary.discard('0');interior=(nodes|cap_nodes)-boundary-{'0'}
    if any(r[1]&interior for r in omitted_primitives):raise ValueError('omitted primitive touches interior')
    kept_names={r[0] for r in kept}
    if any(r[1]&interior for r in caps if r[0] not in kept_names):raise ValueError('omitted capacitor touches interior')
    ports=sorted(boundary);top='IntegerPLL_KeeperConditionalDCO'
    model='\n'.join(['* Conditional only: every exterior connection must be supplied by a validated environment.','.subckt '+top+' '+' '.join(ports),*[r[2] for r in chosen],*[r[2] for r in kept],'.ends '+top])+'\n'
    # Every retained electrical card is an unchanged source card, in source order.
    emitted=[line for line in model.splitlines() if line and line[0] in 'XC']
    if emitted!=[r[2] for r in chosen]+[r[2] for r in kept]:raise ValueError('retained cards changed')
    return model,dict(boundary_ports=ports,interior_nodes=sorted(interior),selected_primitive_names=sorted(selected),retained_capacitor_names=[r[0] for r in kept],omitted_primitive_count=len(omitted_primitives),omitted_nonzero_capacitor_count=len(caps)-len(kept),source_nonzero_capacitor_count=len(caps),all_retained_cards_unchanged=True,no_omitted_branch_touches_interior=True,default_boundary_sources_added=False,supply_current_equivalence_claimed=False,standalone_executable=False,environment_validated=False,model_qualified=False,release_ready=False)

def run(flat,boundary,drivers,output):
    receipts=[p/'assessment.json' for p in [boundary,drivers]];values=[json.loads(p.read_text()) for p in receipts]
    for r in values:verify(r['input_sha256']);verify(r['artifacts'])
    source=flat/'capacitance.spice'
    for r in values:
        if r['input_sha256'].get(str(source))!=sha(source):raise ValueError('same checked source required')
    detail=boundary/'boundary.json';chains=drivers/'chains.json';selected=set(json.loads(detail.read_text())['selected_primitives'])|set(json.loads(chains.read_text())['retained_MOS_cards'])
    files=[*receipts,source,detail,chains,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_DCO_driver_C_cut.py'),Path(__file__).with_name('native_spice_comments.py')];pins={str(p):sha(p) for p in files}
    model,metrics=partition(source.read_text(),selected);verify(pins);output.mkdir(parents=True,exist_ok=False);circuit=output/'conditional.spice';circuit.write_text(model);save(output/'interface.json',metrics)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [circuit,output/'interface.json']},selected_primitive_count=len(selected),retained_nonzero_capacitor_count=len(metrics['retained_capacitor_names']),boundary_port_count=len(metrics['boundary_ports']),interior_node_count=len(metrics['interior_nodes']),all_retained_cards_unchanged=True,no_omitted_branch_touches_interior=True,standalone_executable=False,environment_validated=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','boundary','drivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','boundary','drivers','output']))
