"""Apply supplied TT conditional pin loads at every omitted routed cone receiver."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v2 import rows
from build_prototype_DCO_rc import decimal


def unescape(n):return re.sub(r'\\(.)',r'\1',n).lstrip('\\')


def wire_names(text,bound,metadata):
    names={token:port for port,token in metadata['interface_source_terminals'].items()}
    actual={f[0]:f for line in rows(subcircuits(text)['prototype_BBPD_receiver_RC'])[1:-1] for f in [line.split()] if f[0].startswith('Rwire')}
    index=0
    for net in bound['networks']:
        for r in net['resistors']:
            f=actual.pop('Rwire'+str(index));index+=1
            if F(f[3])!=F(r['ohms']):raise ValueError('serialized wire resistance changed')
            for token,node in zip(r['nodes'],f[1:3]):
                if token in names and names[token]!=node:raise ValueError('wire node identity differs')
                names[token]=node
    if actual:raise ValueError('extra wire resistors')
    return names


def run(source,wire,inventory,route,joined,output):
    receipts=[p/'assessment.json' for p in (source,wire,inventory,route)]
    r,w,i,rt=[json.loads(p.read_text()) for p in receipts]
    for record in (r,w,i,rt):verify(record['artifacts'])
    if r['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]) or w['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]) or w['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):raise ValueError('wire/inventory/route lineage mismatch')
    model=source/'receiver_RC.spice';metadata=source/'model.json';networks=wire/'networks.json';routed=inventory/'routed.json'
    text=model.read_text();m=json.loads(metadata.read_text());bound=json.loads(networks.read_text())
    names=wire_names(text,bound,m);module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells={unescape(n):c for n,c in module['cells'].items()}
    jr=joined/'assessment.json';j=json.loads(jr.read_text());verify(j['artifacts'])
    joinfile=joined/'join.json'
    for row in json.loads(joinfile.read_text())['mapping']:
        name=unescape(row['routed_instance'])
        if name not in cells and '__diode_' in row['master']:
            cells[name]=dict(type=row['master'],port_directions={'DIODE':'input'})
    base=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs';common=base/'timing/sky130_fd_sc_hs__common.lib.json'
    if json.loads(common.read_text())['comp_attribute,capacitive_load_unit']!=[1,'pf']:raise ValueError('supplied pin capacitance units changed')
    paths=[*receipts,jr,joinfile,model,metadata,networks,routed,common,Path(__file__).resolve(),Path(__file__).with_name('build_prototype_DCO_rc.py')];loads=[];seen=set()
    for net in bound['networks']:
        for term in net['outside_terminals']:
            if term['kind']!='I' or term['direction']!='I':continue
            token=term['node']
            if token in seen:raise ValueError('omitted receiver occurs twice')
            seen.add(token);inst,pin=token.rsplit(':',1);cell=cells[unescape(inst)];master=cell['type']
            if cell['port_directions'][pin]!='input' or token not in names:raise ValueError('omitted receiver binding differs')
            family=master.split('__')[1].rsplit('_',1)[0]
            if family=='diode':
                files=[Path(p) for p in rt['input_sha256'] if p.endswith('/antenna_diode_load.lib')]
                if len(files)!=1 or pin!='DIODE':raise ValueError('explicit diode pin model required')
                file=files[0];values=re.findall(r'(?<!\w)capacitance\s*:\s*([0-9.eE+-]+)\s*;',file.read_text())
                if len(values)!=1:raise ValueError('unique diode capacitance required')
                value=F(values[0])/10**12
            else:
                candidates=[base/'cells'/family/(master+'__tt_025C_1v80'+suffix) for suffix in ('_ccsnoise.lib.json','.lib.json')]
                file=next((p for p in candidates if p.exists()),None)
                if file is None:raise ValueError('supplied pin model missing')
                data=json.loads(file.read_text())['pin,'+pin]
                if data['direction']!='input':raise ValueError('supplied pin direction differs')
                values=[F(str(data[k])) for k in ('capacitance','rise_capacitance','fall_capacitance') if k in data]
                if not values:raise ValueError('supplied pin capacitance missing')
                value=max(values)/10**12
            if value<0:raise ValueError('negative pin capacitance')
            paths.append(file);loads.append(dict(spef_terminal=token,spice_node=names[token],master=master,pin=pin,farads=str(value)))
    if not loads:raise ValueError('omitted receiver loads required')
    top='prototype_BBPD_receiver_RC';blocks=subcircuits(text);root=rows(blocks[top]);added=[f'Coutside{i} {x["spice_node"]} VGND {decimal(F(x["farads"]))}' for i,x in enumerate(loads)]
    blocks[top]='\n'.join(root[:-1]+added+root[-1:])+'\n';result=''.join(blocks.values())
    check=[line for line in rows(subcircuits(result)[top]) if line.startswith('Coutside')]
    if len(check)!=len(loads):raise ValueError('outside pin serialization incomplete')
    for line,load in zip(check,loads):
        f=line.split()
        if f[1:3]!=[load['spice_node'],'VGND'] or F(f[3])!=F(load['farads']):raise ValueError('outside pin serialization differs')
    output.mkdir(parents=True,exist_ok=False);target=output/'receiver_RC.spice';target.write_text(result);detail=output/'loads.json';save(detail,loads)
    copied=output/'model.json';save(copied,dict(m,conditional_outside_receiver_pins=len(loads)))
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (target,detail,copied)},
        conditional_outside_receiver_pins=len(loads),all_omitted_input_terminals_on_selected_wire_networks_loaded=True,
        supplied_TT25_conditional_pin_capacitances_used=True,actual_native_PVT_pin_impedance_included=False,
        off_network_aggressors_remain_explicit=True,external_macro_port_loading_included=False,
        native_path_correlation_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','wire','inventory','route','joined','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.wire.resolve(),a.inventory.resolve(),a.route.resolve(),a.joined.resolve(),a.output.resolve())
