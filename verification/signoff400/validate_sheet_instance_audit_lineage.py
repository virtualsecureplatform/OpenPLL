#!/usr/bin/env python3
"""Bind independent instance/matrix checks to all semantic source metadata."""
import argparse
import json
from pathlib import Path
from common import save,sha

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('instances','audit','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();root=a.instances.resolve();audit=a.audit.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    producer=root/'assessment.json';auditor=audit/'assessment.json'
    r=json.loads(producer.read_text());v=json.loads(auditor.read_text())
    if not v['all_instances_independently_checked'] or not v['exact_saved_element_matrices_reconstructed'] or v['input_sha256'].get(str(producer))!=sha(producer):
        raise ValueError('matching complete instance/element audit required')
    paths=[Path(r[k])/'assessment.json' for k in ('source_inventory','source_geometry','source_contours','source_roles')]
    paths.extend((Path(r['source_contours'])/'polygons.jsonl',Path(r['source_roles'])/'field_role_intervals.json'))
    pins={str(producer):sha(producer),str(auditor):sha(auditor),str(Path(__file__).resolve()):sha(Path(__file__))}
    for path in paths:
        h=sha(path)
        if r['input_sha256'].get(str(path))!=h:raise ValueError('semantic geometry/role dependency changed: '+str(path))
        pins[str(path)]=h
    for name in ('nominal_sheet_rules.json','atlas/requests.json','atlas/template_aliases.json','atlas/templates.jsonl'):
        path=root/name;h=sha(path)
        if r['artifacts'][str(path)]!=h or v['input_sha256'].get(str(path))!=h:raise ValueError('audited atlas metadata changed')
        pins[str(path)]=h
    requests=json.loads((root/'atlas/requests.json').read_text())
    if [q['global_template_id'] for q in requests]!=list(range(len(requests))):raise ValueError('atlas request global IDs differ from positions')
    aliases=json.loads((root/'atlas/template_aliases.json').read_text())
    if any(not 0<=q['global_template_id']<len(requests) for q in aliases):raise ValueError('invalid atlas alias')
    save(out/'assessment.json',dict(input_sha256=pins,all_instance_and_matrix_checks_bound_to_semantic_inputs=True,
         basis_instances=v['basis_instances'],unique_geometry_templates=v['unique_geometry_templates'],atlas_variants=v['atlas_variants'],
         logical_floating_basis_nodes_by_refinement=v['logical_floating_basis_nodes_by_refinement'],
         arithmetic_ids_preserved_without_states=v['arithmetic_ids_preserved_without_states'],
         charge_projection_complete=False,nominal_sheet_reference_temperature_known=False,resistance_PVT_qualified=False,
         physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
    print(json.dumps(dict(status='pass',basis_instances=v['basis_instances'],all_semantic_dependencies_bound=True)))
