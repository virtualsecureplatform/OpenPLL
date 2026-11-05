"""Attach a geometrically witnessed forming-stage receiver to a same-route ECO.

This prepares a repair only. Both native and independent forming-stage antenna
checks must be repeated on the resulting physical geometry.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify


def run(plan,route,witness,output):
    pp=plan/'plan.json';rr=route/'assessment.json';wr=witness/'assessment.json'
    p,r,w=[json.loads(f.read_text()) for f in (pp,rr,wr)]
    for record in (p,r,w):
        verify(record['input_sha256'])
        if 'artifacts' in record:verify(record['artifacts'])
    db=route/'route.odb';gds=route/'signoff/route.gds'
    if (p['route_sha256']!=sha(db)
            or not w.get('unique_geometric_receiver_identified')
            or any(w['input_sha256'].get(str(f))!=sha(f) for f in (db,gds))
            or p.get('antenna_targets')):
        raise ValueError('same-route unique receiver and no prior diode proposal required')
    receiver=witness/'receiver.json'
    if w['artifacts'].get(str(receiver))!=sha(receiver):
        raise ValueError('unbound receiver witness')
    evidence=json.loads(receiver.read_text());target=evidence['receiver']
    formation=evidence['formation'];intersections=evidence['physical_pin_intersections']
    if (not formation['violation'] or formation['ratio']<=formation['allowed_ratio']
            or not intersections
            or any(x['pin']!=target['pin'] or x['net']!=target['net'] or x['intersection_nm2']<=0
                   for x in intersections)):
        raise ValueError('positive physical overlap with the violating component required')
    inputs=dict(p['input_sha256'])
    inputs.update({str(f):sha(f) for f in (pp,rr,wr,receiver,Path(__file__).resolve())})
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    p.update(input_sha256=inputs,antenna_targets=[[target['net'],target['cell'],target['pin']]],
             measured_forming_receiver_pins=1,antenna_closure_claimed=False,
             independent_postroute_antenna_recheck_required=True,release_ready=False)
    save(output/'plan.json',p)
    print(json.dumps(dict(measured_forming_receiver_pins=1)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('plan','route','witness','output'):parser.add_argument('--'+n,type=Path,required=True)
    a=parser.parse_args();run(*(getattr(a,n).resolve() for n in ('plan','route','witness','output')))
