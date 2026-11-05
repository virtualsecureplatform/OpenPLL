"""Audit physical basis and internal driver-anchor policy across DCO models.

Matching GDS, nominal wire values and internal attachment representatives does
not establish equality of capacitance operators or external driver/loading.
"""
import argparse,json
from fractions import Fraction
from pathlib import Path
from common_v3 import save,sha,verify


def compare(child,wire_map,terms):
    rows=[];external=0
    for net in child['networks']:
        if any(t['ideal_supply_boundary'] for t in net['terminals']):continue
        if any(t['kind']=='P' and t['direction']=='I' for t in net['terminals']):external+=1;continue
        drivers=sorted((t for t in net['terminals'] if t['kind']=='I' and t['direction']=='O'),key=lambda t:t['node'])
        if not drivers:continue
        def actual(t):
            nodes={terms[name][index] for name,index in t['primitive_terminal_positions']}
            if len(nodes)!=1:raise ValueError('unique physical output contact required')
            return next(iter(nodes))
        anchor=wire_map['capacitor_anchors'].get(net['context_conductor'],net['context_conductor'])
        expected=actual(drivers[0]);selected=[t['node'] for t in drivers if actual(t)==anchor]
        rows.append(dict(net=net['net'],parallel_drivers=len(drivers),standalone_policy_first_output=drivers[0]['node'],
                         first_output_full_model_contact=expected,full_model_capacitor_anchor=anchor,
                         full_model_selected_driver_tokens=selected,same_internal_driver_anchor=expected==anchor))
    return rows,external


def run(isolated_receipt,isolated_model,nominal_spef,full_receipt,child,output):
    if output.exists():raise FileExistsError(output)
    ir=json.loads(isolated_receipt.read_text());fr=json.loads(full_receipt.read_text())
    if ir.get('attachment')!='driver' or fr.get('attachment')!='driver' or fr.get('wire_corner')!='nom':raise ValueError('driver attachment and nominal full-model wires required')
    if ir['assembled_candidate_gds_sha256']!=fr['assembled_candidate_gds_sha256']:raise ValueError('different assembled manufacturing candidates')
    if ir['artifacts'].get(str(isolated_model))!=sha(isolated_model):raise ValueError('isolated model artifact changed')
    verify(fr['artifacts'])
    if fr['input_sha256'].get(str(child))!=sha(child):raise ValueError('child wire basis changed')
    wire_map=full_receipt.parent/'wire_map.json';wire=full_receipt.parent/'context.spice'
    if str(wire_map) not in fr['artifacts'] or str(wire) not in fr['artifacts']:raise ValueError('proved wire graph and map required')
    spef=json.loads(nominal_spef.read_text());expected=[Fraction(str(r['ohms'])) for n in spef['nets'] for r in n['resistors']]
    resistors={}
    for line in isolated_model.open():
        if line.startswith('Rwire'):
            f=line.split();index=int(f[0][5:])
            if index in resistors or len(f)!=4:raise ValueError('unique literal isolated wire cards required')
            resistors[index]=Fraction(f[3])
    if set(resistors)!=set(range(len(expected))):raise ValueError('isolated wire resistor count differs from nominal SPEF')
    relative=[float(abs(resistors[i]-r)/r) for i,r in enumerate(expected)]
    if max(relative,default=0)>1e-12:raise ValueError('isolated wire values differ from nominal SPEF')
    terms={}
    for line in wire.open():
        if not line.startswith('Xflat'):continue
        f=line.split();stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'))
        if f[0] in terms:raise ValueError('duplicate physical primitive')
        terms[f[0]]=f[1:stop]
        if len(terms)==62450:break
    if len(terms)!=62450:raise ValueError('complete selected native primitive graph required')
    rows,external=compare(json.loads(child.read_text()),json.loads(wire_map.read_text()),terms)
    pins={str(p):sha(p) for p in [isolated_receipt,isolated_model,nominal_spef,full_receipt,child,wire_map,wire,Path(__file__).resolve()]}
    verify(pins)
    save(output,dict(input_sha256=pins,same_assembled_candidate=True,
        assembled_candidate_gds_sha256=ir['assembled_candidate_gds_sha256'],
        isolated_nominal_wire_resistors=len(expected),maximum_wire_value_relative_difference=max(relative,default=0),
        internal_driver_networks_compared=len(rows),different_internal_driver_anchors=sum(not x['same_internal_driver_anchor'] for x in rows),
        internal_driver_anchors=rows,externally_driven_child_input_networks_not_compared=external,
        capacitance_operator_equivalence_validated=False,external_driver_impedance_equivalence_validated=False,
        initial_history_equivalence_validated=False,frequency_correlation_qualified=False,release_ready=False))
    print(json.dumps(dict(internal_driver_networks=len(rows),different_internal_driver_anchors=sum(not x['same_internal_driver_anchor'] for x in rows),nominal_wire_resistors=len(expected),external_input_networks_not_compared=external)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['isolated-receipt','isolated-model','nominal-spef','full-receipt','child','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['isolated-receipt','isolated-model','nominal-spef','full-receipt','child','output']))
