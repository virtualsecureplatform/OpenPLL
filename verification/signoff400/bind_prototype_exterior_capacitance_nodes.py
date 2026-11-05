"""Bind exterior capacitor boundaries to a completed model's voltage map.

This binds capacitor attachment points, not distributed physical wire locations.
No exterior terminal is grounded; no partial capacitor matrix is stamped.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_analog_reference import subcircuits


def bindings(boundaries, target, voltage, live_nodes):
    result=[];parent={}
    for row in boundaries:
        pin=row['pin']
        keys=[n for n in (pin,target+'/'+pin) if n in voltage]
        points={voltage[n] for n in keys}
        if len(points)!=1:raise ValueError('unique original capacitor voltage required: '+pin)
        point=next(iter(points))
        if point not in live_nodes:raise ValueError('attachment point absent from reduced model: '+pin)
        node=row['node']
        if node in parent and parent[node]!=point:
            raise ValueError('one exterior conductor maps to conflicting attachment points')
        parent[node]=point
        result.append(dict(**row,capacitor_attachment_node=point,original_voltage_keys=keys))
    return result,parent


def nodes(text):
    found=set()
    for line in text.splitlines():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':found.update(f[2:])
        elif f[0].startswith(('Cflat','Ckron','Rwire')):found.update(f[1:3])
        elif f[0].startswith('Xflat'):
            for token in f[1:]:
                if token.startswith('sky130_fd_pr__'):break
                found.add(token)
    return found


def run(boundary,node_map,reduced,output):
    receipts=[p/'assessment.json' for p in (boundary,node_map,reduced)]
    br,nr,rr=records=[json.loads(p.read_text()) for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    if not br.get('canonical_supply_aliases_excluded_from_signal_boundary'):
        raise ValueError('supply aliases must be excluded before binding')
    if not nr['exact_completed_model_bytes_reproduced'] or nr['attachment']!=rr['attachment']:
        raise ValueError('matching completed node-map replay required')
    if not rr['bounded_floating_C_terminal_reduction_verified'] or not rr['each_fixed_supply_dynamic_C_operator_passivity_certified']:
        raise ValueError('bounded passive reduced model required')
    for path,digest in rr['assembled_candidate_gds_sha256'].items():
        if br['input_sha256'].get(path)!=digest:raise ValueError('assembled GDS differs')
    common={p for p,h in nr['input_sha256'].items() if rr['input_sha256'].get(p)==h and p.endswith('/assessment.json')}
    source=[p for p in common if json.loads(Path(p).read_text()).get('capacitance_lifts_are_exact_matrix_congruences')]
    if len(source)!=1:raise ValueError('one common full-C construction receipt required')
    bp=boundary/'boundary.json';np=node_map/'nodes.json';model=reduced/(rr['attachment']+'.spice')
    paths=[*receipts,bp,np,model,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths}
    data=json.loads(bp.read_text());mapping=json.loads(np.read_text())
    text=model.read_text();blocks=subcircuits(text)
    if set(blocks)!={data['target']}:raise ValueError('oscillator hierarchy identity differs')
    rows,parents=bindings(data['boundaries'],data['target'],mapping['original_capacitance_node_to_emitted_node'],nodes(text))
    if len(rows)!=data['physical_macro_boundary_pins']+data['exported_internal_boundary_pins']:
        raise ValueError('incomplete boundary inventory')
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'bindings.json',dict(attachment=rr['attachment'],boundaries=rows,
        exterior_conductor_to_capacitor_attachment=parents,
        physical_macro_boundary_pins=data['physical_macro_boundary_pins'],
        exported_internal_boundary_pins=data['exported_internal_boundary_pins']))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'bindings.json'):sha(output/'bindings.json')},
        attachment=rr['attachment'],all_signal_capacitor_boundaries_bound=True,
        remote_coupling_endpoints_grounded=False,exterior_capacitance_stamped=False,
        physical_wire_location_binding_claimed=False,parent_loading_complete=False,
        validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('boundary','node-map','reduced','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.boundary.resolve(),a.node_map.resolve(),a.reduced.resolve(),a.output.resolve())
