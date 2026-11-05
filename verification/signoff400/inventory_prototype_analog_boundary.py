"""Inventory every non-supply analog boundary in the checked assembled hierarchy.

Retain signed coupling endpoints and actual exterior device cards. No remote
terminal is grounded and no lumped load or model qualification is inferred.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify
from prototype_capacitance_aliases_v2 import flatten
from bind_prototype_spef_pins_v2 import hierarchy
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v3 import header

RAILS={'0','VGND','VNB','VPWR','VPB'}


def inventory(text,top,target,physical_pins):
    blocks=subcircuits(text);ports,instances,find=hierarchy(text,top)
    selected=[v for v in instances.values() if v['model']==target]
    if len(selected)!=1:raise ValueError('one actual analog macro required')
    chosen=selected[0]
    blocks[target]='.subckt '+target+' '+' '.join(header(blocks[target]))+'\n.ends '+target+'\n'
    caps,counts,canonical=flatten(blocks,top)
    def signal(n):
        n=find(n);return canonical(n if n in ports or n=='0' else top+'/'+n)
    fixed={signal(n) for p,n in chosen['pins'].items() if p in RAILS}|{'0'}
    boundary={p:signal(n) for p,n in chosen['pins'].items() if p not in RAILS and signal(n) not in fixed}
    reverse={}
    for pin,node in boundary.items():reverse.setdefault(node,[]).append(pin)
    rows=[dict(nodes=list(pair),farads=str(value),boundary_pins=sorted({p for n in pair for p in reverse.get(n,[])}))
          for pair,value in sorted(caps.items()) if set(pair)&reverse.keys()]
    def device_name(n):return '/'.join(p[1:] if p.startswith('Xsky130_fd_sc_hd__') else p for p in n.split('/'))
    active_names={device_name(n):pins for n,pins in reverse.items()};active=[]
    for (model,nodes,parameters),count in sorted(devices(blocks,top).items()):
        pins=sorted({p for node in nodes for p in active_names.get(node,[])})
        if pins:active.append(dict(model=model,nodes=list(nodes),parameters=dict(parameters),count=count,boundary_pins=pins))
    return dict(top=top,target=target,boundaries=[dict(pin=p,node=n,physical_macro_pin=p in physical_pins,
                    exported_internal_node=p not in physical_pins) for p,n in sorted(boundary.items())],
        exterior_counts=counts,signed_incident_capacitors=rows,exterior_incident_devices=active,
        physical_macro_boundary_pins=sum(p in physical_pins for p in boundary),
        exported_internal_boundary_pins=sum(p not in physical_pins for p in boundary),
        incident_geometric_pairs=len(rows),incident_exterior_primitive_instances=sum(r['count'] for r in active),
        exterior_capacitances_not_grounded=True,intrinsic_device_capacitance_evaluated=False,
        passivity_of_isolated_exterior_not_assumed=True,parent_loading_complete=False,release_ready=False)


def run(extraction,converted,frame,layout,role,output):
    er=extraction/'native_assessment.json';cr=converted/'assessment.json';fr=frame/'assessment.json';lr=layout/'assessment.json'
    e,c,f,l=[json.loads(p.read_text()) for p in (er,cr,fr,lr)]
    # Run inside the pinned image, where native tool and PDK pins are visible.
    for record in (e,c,f,l):verify(record['input_sha256']);verify(record['artifacts'])
    gds=layout/'assembly.gds'
    if l['input_sha256'].get(str(fr))!=sha(fr) or e['input_sha256'].get(str(gds))!=sha(gds):
        raise ValueError('native extraction and physical frame must bind the same assembled GDS')
    source=extraction/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if (e['artifacts'].get(str(source))!=sha(source) or c['input_sha256'].get(str(source))!=sha(source)
            or not c['exact_expanded_conversion_reparse_pass']):raise ValueError('same native hierarchy and exact unit conversion required')
    if role not in ('oscillator','detector'):raise ValueError('supported analog role required')
    physical=f['macro_sources'][role];lef=Path(physical['lef']);model=converted/'ng47.spice'
    pins=set(re.findall(r'^\s*PIN\s+(\S+)\s*$',lef.read_text(),re.M))
    if not pins:raise ValueError('physical LEF port inventory required')
    inputs={str(p):sha(p) for p in (er,cr,fr,lr,gds,source,model,lef,Path(__file__).resolve(),
        Path(__file__).with_name('prototype_capacitance_aliases_v2.py'),Path(__file__).with_name('native_spice_comments.py'),
        Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('bind_prototype_spef_pins_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py'),Path(__file__).with_name('prepare_prototype_BBPD_receiver_v3.py'))}
    result=inventory(model.read_text(),'IntegerPLL_400MHz_PrototypeTop',physical['master'],pins)
    verify(inputs);output.mkdir(parents=True,exist_ok=False);save(output/'boundary.json',result)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(output/'boundary.json'):sha(output/'boundary.json')},
         role=role,all_non_supply_extracted_boundary_pins_inventoried=True,
         physical_macro_boundary_pins=result['physical_macro_boundary_pins'],
         exported_internal_boundary_pins=result['exported_internal_boundary_pins'],
         native_diode_effective_units_applied=True,stock_native_fill_type_exterior_only=True,diagnostic=True,parent_loading_complete=False,release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','converted','frame','layout','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--role',choices=('oscillator','detector'),required=True)
    a=parser.parse_args();run(a.extraction.resolve(),a.converted.resolve(),a.frame.resolve(),a.layout.resolve(),a.role,a.output.resolve())
