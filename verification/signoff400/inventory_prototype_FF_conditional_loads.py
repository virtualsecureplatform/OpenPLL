"""Account for every FF receiver pin and wire C; supplied TT pin caps are diagnostic."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
from common_v3 import ROOT, save, sha, verify
from prototype_spef_v2 import parse
from inventory_prototype_FF_wire_loads import unescape


def run(route, joined, loads, output):
    receipts=[p/'assessment.json' for p in (route,joined,loads)]
    r,j,l=[json.loads(p.read_text()) for p in receipts]
    for record in (r,j,l):verify(record['artifacts'])
    spef=route/'route.nom.spef';mapping=joined/'join.json';outputs=loads/'outputs.json'
    if l['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or l['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('wire inventory route/join lineage mismatch')
    masters={unescape(row['routed_instance']):row['master'] for row in json.loads(mapping.read_text())['mapping']}
    source=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs'
    common=source/'timing/sky130_fd_sc_hs__common.lib.json'
    if json.loads(common.read_text())['comp_attribute,capacitive_load_unit']!=[1,'pf']:
        raise ValueError('supplied pin capacitance units changed')
    pins={str(p):sha(p) for p in (*receipts,spef,mapping,outputs,common,Path(__file__).resolve(),
          Path(__file__).with_name('prototype_spef_v2.py'),Path(__file__).with_name('inventory_prototype_FF_wire_loads.py'))}
    cache={}
    diode_files=[Path(p) for p in r['input_sha256'] if p.endswith('/antenna_diode_load.lib')]
    def capacitance(master,pin):
        if (master,pin) in cache:return cache[master,pin]
        family=master.split('__')[1].rsplit('_',1)[0]
        if family=='diode':
            if len(diode_files)!=1:raise ValueError('explicit diode load screen required')
            p=diode_files[0];text=p.read_text()
            if master!='sky130_fd_sc_hs__diode_2' or pin!='DIODE':raise ValueError('unreviewed diode load')
            values=re.findall(r'(?<!\w)capacitance\s*:\s*([0-9.eE+-]+)\s*;',text)
            if len(values)!=1:raise ValueError('unique diode input capacitance required')
            value=F(values[0])
        else:
            candidates=[source/'cells'/family/(master+'__tt_025C_1v80'+suffix)
                        for suffix in ('_ccsnoise.lib.json','.lib.json')]
            p=next((p for p in candidates if p.exists()),None)
            if p is None:raise ValueError('missing supplied input pin model: '+master)
            data=json.loads(p.read_text())['pin,'+pin]
            if data['direction']!='input':raise ValueError('SPEF receiver is not a library input')
            values=[F(str(data[k])) for k in ('capacitance','rise_capacitance','fall_capacitance') if k in data]
            if not values:raise ValueError('missing receiver pin capacitance')
            value=max(values)
        if value<0:raise ValueError('negative supplied receiver capacitance')
        pins[str(p)]=sha(p);cache[master,pin]=value/10**12
        return cache[master,pin]
    nets=parse(spef.read_text())['nets'];by_driver={}
    for net in nets:
        for t in net['connections']:
            if t['kind']=='I' and t['direction']=='O':
                name,pin=t['node'].rsplit(':',1)
                if pin=='Q':
                    name=unescape(name)
                    if name in by_driver:raise ValueError('multiple FF Q wire networks')
                    by_driver[name]=net
    result=[]
    for row in json.loads(outputs.read_text()):
        net=by_driver[row['routed_instance']];receivers=[];external=[]
        for t in net['connections']:
            if t['kind']=='P':external.append(t);continue
            if t['direction']!='I':continue
            name,pin=t['node'].rsplit(':',1);master=masters[unescape(name)]
            receivers.append(dict(terminal=t['node'],master=master,pin=pin,
                                  supplied_TT_pin_capacitance_F=str(capacitance(master,pin))))
        pin_sum=sum((F(x['supplied_TT_pin_capacitance_F']) for x in receivers),F())
        ground=F(row['sum_ground_wire_capacitance_F']);coupling=F(row['sum_coupling_records_F'])
        result.append(dict(row,receivers=receivers,macro_boundary_terminals=external,
             supplied_TT_receiver_pin_sum_fF=float(pin_sum*10**15),
             quiet_aggressor_conditional_load_fF=float((ground+coupling+pin_sum)*10**15),
             opposite_full_swing_charge_equivalent_fF=float((ground+2*coupling+pin_sum)*10**15),
             coupling_charge_equivalent_is_not_a_delay_or_peak_current_bound=True,
             external_macro_port_loading_included=False))
    groups={m:max(x['quiet_aggressor_conditional_load_fF'] for x in result if x['master']==m)
            for m in {x['master'] for x in result}}
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'outputs.json';save(detail,result)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         all_FF_output_receiver_terminals_accounted_for=True,FF_outputs=len(result),
         maximum_quiet_aggressor_conditional_load_fF_by_master=groups,
         supplied_TT25_input_capacitance_only=True,native_PVT_pin_capacitances_qualified=False,
         macro_boundary_loading_complete=False,final_load_envelope_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','joined','loads','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.joined.resolve(),a.loads.resolve(),a.output.resolve())
