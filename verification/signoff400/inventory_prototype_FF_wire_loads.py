"""Inventory routed FF output wire capacitance; cell pins/final parent fill remain separate."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import re
from common import save,sha,verify
from prototype_spef_v2 import parse


def unescape(name):return re.sub(r'\\(.)',r'\1',name)


def run(route,joined,output):
    output.mkdir(parents=True,exist_ok=False)
    rr=route/'assessment.json';jr=joined/'assessment.json';r,j=[json.loads(p.read_text()) for p in (rr,jr)]
    spef=route/'route.nom.spef';mapping=joined/'join.json'
    for path,receipt in ((spef,r),(mapping,j)):
        if receipt['artifacts'].get(str(path))!=sha(path):raise ValueError('wire-load input changed')
    source=parse(spef.read_text())
    if not source['pin_capacitance_excluded']:raise ValueError('declared PIN_CAP NONE required')
    masters={}
    for row in json.loads(mapping.read_text())['mapping']:
        name=unescape(row['routed_instance'])
        if name in masters:raise ValueError('ambiguous routed instance escape normalization')
        masters[name]=row['master']
    wanted={n for n,m in masters.items() if '__dfrtp_' in m or '__dfstp_' in m}
    records=[];found=set()
    for net in source['nets']:
        for term in net['connections']:
            if term['kind']!='I':continue
            name,pin=term['node'].rsplit(':',1);name=unescape(name)
            if name not in wanted or pin!='Q':continue
            if name in found:raise ValueError('FF Q appears in multiple SPEF nets')
            if term['direction']!='O':raise ValueError('FF Q is not an extracted output driver')
            found.add(name)
            # Coupled pairs are listed per owning net; do not sum across owners here.
            ground=sum((F(c['farads']) for c in net['capacitors'] if len(c['nodes'])==1),F())
            coupling=sum((F(c['farads']) for c in net['capacitors'] if len(c['nodes'])==2),F())
            records.append(dict(routed_instance=name,master=masters[name],net=net['name'],
                 declared_wire_capacitance_F=net['declared_capacitance_F'],
                 sum_ground_wire_capacitance_F=str(ground),sum_coupling_records_F=str(coupling),
                 receiver_terminals=sum(c['direction']=='I' for c in net['connections']),
                 total_receiver_pin_capacitance_included=False))
    if found!=wanted:raise ValueError('not every routed FF output is covered: '+str(sorted(wanted-found)))
    groups=defaultdict(list)
    for row in records:groups[row['master']].append(F(row['declared_wire_capacitance_F']))
    summary={m:dict(instances=len(v),minimum_declared_wire_capacitance_fF=float(min(v)*10**15),
                   maximum_declared_wire_capacitance_fF=float(max(v)*10**15),
                   outputs_above_20fF_wire_alone=sum(x>F(20,10**15) for x in v)) for m,v in sorted(groups.items())}
    paths=[rr,jr,spef,mapping,Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py')]
    pins={str(p):sha(p) for p in paths};detail=output/'outputs.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         routed_FF_outputs=len(records),by_master=summary,pin_capacitance_excluded=True,
         parent_and_final_fill_loading_included=False,timing_load_envelope_qualified=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('route','joined','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.joined.resolve(),a.output.resolve())
