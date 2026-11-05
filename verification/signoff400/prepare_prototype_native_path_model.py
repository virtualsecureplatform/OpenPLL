"""Bind a selected routed timing cone to exact extracted standard-cell instances."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v3 import header,identifier
from bind_prototype_spef_pins_v2 import hierarchy


def run(selection,inventory,joined,route,extraction,output):
    dirs=[selection,inventory,joined,route,extraction];receipts=[d/'assessment.json' for d in dirs]
    s,i,j,r,e=[json.loads(p.read_text()) for p in receipts]
    files=[selection/'selection.json',inventory/'routed.json',joined/'join.json',route/'route.v',extraction/'IntegerPLL_ProgrammedCore/capacitance.spice']
    for p,record in zip(files,(s,i,j,r,e)):
        if record['artifacts'].get(str(p))!=sha(p):raise ValueError('selected path source changed')
    if s['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]) or e['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):
        raise ValueError('path inventory or extraction lineage mismatch')
    top_ext=files[-1].parent/'IntegerPLL_ProgrammedCore.ext'
    if j['input_sha256'].get(str(top_ext))!=sha(top_ext):raise ValueError('instance join belongs to another extraction')
    module=json.loads(files[1].read_text())['modules']['IntegerPLL_ProgrammedCore']
    chosen=json.loads(files[0].read_text());join={identifier(row['routed_instance']):row for row in json.loads(files[2].read_text())['mapping']}
    blocks=subcircuits(files[-1].read_text());_,physical,canonical=hierarchy(files[-1].read_text(),'IntegerPLL_ProgrammedCore')
    definitions={};instances=[];bindings=[];logical={};inverse={}
    for index,name in enumerate(chosen['cells']):
        cell=module['cells'][name];row=join[identifier(name)];actual=physical[row['extracted_instance']]
        if cell['type']!=row['master'] or actual['model']!=cell['type']:raise ValueError('physical cell master mismatch')
        pinmap={}
        for pin,bits in cell['connections'].items():
            if len(bits)!=1 or not isinstance(bits[0],int):raise ValueError('scalar nonconstant functional conductor required')
            bit=bits[0];node=canonical(actual['pins'][pin])
            if logical.setdefault(bit,node)!=node or inverse.setdefault(node,bit)!=bit:raise ValueError('logical/physical conductor split or short')
            pinmap[pin]='n_'+str(bit)
        pinmap.update(VPWR='VPWR',VGND='VGND',VPB='VPB',VNB='VNB')
        block=blocks[cell['type']];ports=header(block);private=[p for p in ports if p not in pinmap]
        if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in private):raise ValueError('unreviewed private cell terminal')
        definitions[cell['type']]=block
        instances.append('Xreceiver_'+str(index)+' '+' '.join(pinmap.get(p,'private_'+str(index)+'_'+str(k)) for k,p in enumerate(ports))+' '+cell['type'])
        bindings.append(dict(routed_instance=name,extracted_instance=row['extracted_instance'],master=cell['type'],functional_pins=pinmap,private_extracted_ports=private))
    observed=[]
    for name in (chosen['data_path'][0],chosen['data_path'][-1]):
        for pin in ('CLK','D','Q'):observed.extend(module['cells'][name]['connections'][pin])
    interface=['n_'+str(b) for b in sorted(set(chosen['boundary_bits']+observed))]+['VGND','VNB','VPB','VPWR']
    metadata=dict(chosen,interface=interface,physical_bindings=bindings,
        boundaries=[dict(bit=b,aliases=[dict(name=n,index=k) for n,v in module['netnames'].items() for k,x in enumerate(v['bits']) if x==b]) for b in chosen['boundary_bits']],
        observed_endpoint_bits=sorted(set(observed)))
    output.mkdir(parents=True,exist_ok=False);model=output/'receiver.spice';detail=output/'receiver.json'
    model.write_text('* Native timing path cone; cell-local C, wire RC added separately.\n'+''.join(definitions.values())+'\n.subckt prototype_BBPD_receiver '+' '.join(interface)+'\n'+'\n'.join(instances)+'\n.ends prototype_BBPD_receiver\n')
    save(detail,metadata)
    paths=[*receipts,*files,top_ext,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_BBPD_receiver_v3.py'),Path(__file__).with_name('bind_prototype_spef_pins_v2.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (model,detail)},
        selected_cells=len(bindings),physical_cell_and_conductor_binding_pass=True,
        clock_and_data_cell_local_C_retained=True,omitted_receiver_terminals=len(chosen['omitted_receiver_terminals']),
        all_boundary_stimuli_justified=False,intercell_wire_RC_included=False,native_path_correlation_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('selection','inventory','joined','route','extraction','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.selection.resolve(),a.inventory.resolve(),a.joined.resolve(),a.route.resolve(),a.extraction.resolve(),a.output.resolve())
