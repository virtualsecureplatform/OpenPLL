"""Translate a free-output conditional circuit; never invent its external environment."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_keeper_flat_native_v2 import normalize
from run_keeper_flat_native_smoke_v2 import adapt_diodes

def safe_ports(text,interface):
    lines=text.splitlines();headers=[i for i,s in enumerate(lines) if s.lower().startswith('.subckt ')]
    if len(headers)!=1:raise ValueError('one flat scope required')
    h=headers[0];f=lines[h].split();ports=f[2:]
    if ports!=interface['boundary_ports']:raise ValueError('same ordered interface required')
    if interface['observation_only_ports']!=['PLLOUT'] or 'PLLOUT' in interface['externally_driven_ports']:raise ValueError('free output required')
    if set(interface['externally_driven_ports'])|{'PLLOUT'}!=set(ports):raise ValueError('complete explicit interface required')
    mapping={p:'openpll_boundary_'+str(i) for i,p in enumerate(ports)}
    original_nodes=set()
    for line in lines:
        f=line.split()
        if not f:continue
        if f[0].startswith('X'):
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;original_nodes.update(f[1:j])
        elif f[0].startswith('C'):original_nodes.update(f[1:3])
    if set(mapping.values()) & original_nodes:raise ValueError('boundary namespace collision')
    for i,line in enumerate(lines):
        f=line.split()
        if not f:continue
        if i==h:f=[*f[:2],*[mapping[p] for p in ports]]
        elif f[0].startswith('X'):
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;f=[f[0],*[mapping.get(n,n) for n in f[1:j]],*f[j:]]
        elif f[0].startswith('C'):f=[f[0],mapping.get(f[1],f[1]),mapping.get(f[2],f[2]),f[3]]
        else:continue
        lines[i]=' '.join(f)
    return '\n'.join(lines)+'\n',mapping

def run(conditional,smoke,output):
    receipts=[p/'assessment.json' for p in [conditional,smoke]];a,s=[json.loads(p.read_text()) for p in receipts]
    for r in [a,s]:verify(r['input_sha256']);verify(r['artifacts'])
    if not a['PLLOUT_is_observation_only_and_not_externally_driven'] or not a['no_omitted_branch_touches_interior']:raise ValueError('checked free-output conditional circuit required')
    # The existing reset reference supplies the exact same backend/PDK translation provenance.
    raw_sources=[p for p in a['input_sha256'] if p.endswith('/capacitance.spice')]
    full_model=next(Path(p) for p in s['input_sha256'] if Path(p).name=='model.spice')
    model_receipt=json.loads((full_model.parent/'assessment.json').read_text())
    if len(raw_sources)!=1 or model_receipt['input_sha256'].get(raw_sources[0])!=a['input_sha256'][raw_sources[0]]:raise ValueError('same physical flat model required')
    verify(model_receipt['input_sha256']);verify(model_receipt['artifacts'])
    source=conditional/'conditional.spice';detail=conditional/'interface.json';interface=json.loads(detail.read_text());folder=Path(__file__).resolve().parent
    files=[*receipts,source,detail,full_model.parent/'assessment.json',Path(__file__).resolve(),*[folder/n for n in ['prepare_keeper_flat_native_v2.py','run_keeper_flat_native_smoke_v2.py','prototype_native_literal_templates.py','prototype_xyce_resistor_translation.py','convert_prototype_ng47_diode_geometry.py','prototype_xyce_diode_translation.py','native_spice_comments.py','audit_hierarchical_capacitance.py']]]
    pins={**s['input_sha256'],**{str(p):sha(p) for p in files}}
    original=source.read_text();safe,portmap=safe_ports(original,interface);model,nodes,metrics=normalize(safe);adapted,diodes=adapt_diodes(model)
    reverse={v:k for k,v in portmap.items()};physical={reverse.get(n,n):v for n,v in nodes.items()};inverse={v:k for k,v in physical.items()}
    if len(physical)!=len(nodes) or len(inverse)!=len(nodes):raise ValueError('reversible physical node mapping required')
    expected=[s.split() for s in original.splitlines() if s.startswith('C')]
    actual=[s.split() for s in adapted.splitlines() if s.startswith('C')]
    if len(expected)!=len(actual):raise ValueError('C count changed')
    for before,after in zip(expected,actual):
        if [after[0],inverse[after[1]],inverse[after[2]],after[3]]!=before:raise ValueError('C endpoint/value changed')
    binding=dict(observation_only_ports={'PLLOUT':physical['PLLOUT']},externally_driven_ports={n:physical[n] for n in interface['externally_driven_ports']},all_physical_nodes=physical,default_sources_added=False)
    verify(pins);output.mkdir(parents=True,exist_ok=False);model_file=output/'model.spice';model_file.write_text(adapted);save(output/'bindings.json',binding);save(output/'translation.json',dict(normalization=metrics,diodes=diodes))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [model_file,output/'bindings.json',output/'translation.json']},selected_primitive_count=metrics['source_counts']['X'],nonzero_C_endpoints_and_values_exactly_preserved=len(actual),externally_driven_port_count=len(binding['externally_driven_ports']),PLLOUT_not_externally_driven=True,reversible_physical_node_mapping=True,temperature_C=27,default_boundary_sources_added=False,environment_validated=False,native_execution_complete=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['conditional','smoke','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['conditional','smoke','output']))
