"""Check final extracted primitive bulk/supply topology and parameter signs."""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
import time
from common import save,sha,verify
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits
from resources import lease


def check(cards):
    models=Counter();failures=[];mos=diodes=0
    for (model,nodes,parameters),count in cards.items():
        models[model]+=count;params=dict(parameters)
        if 'nfet' in model or 'pfet' in model:
            mos+=count
            bulk={'VGND','VNB'} if 'nfet' in model else {'VPWR','VPB'}
            if len(nodes)!=4 or nodes[3] not in bulk:
                failures.append(dict(model=model,nodes=list(nodes),count=count,reason='MOS bulk not connected to declared polarity supply'))
            for key in ('l','w','ad','as','pd','ps'):
                if key not in params:
                    failures.append(dict(model=model,count=count,reason='missing explicit MOS geometry parameter',parameter=key));continue
                value=F(params[key])
                if value<=0 if key in ('l','w') else value<0:
                    failures.append(dict(model=model,count=count,reason='nonphysical MOS dimension/junction sign',parameter=key,value=str(value)))
        elif model=='sky130_fd_pr__diode_pw2nd_05v5':
            diodes+=count
            if len(nodes)!=2 or nodes[0] not in {'VGND','VNB'}:
                failures.append(dict(model=model,nodes=list(nodes),count=count,reason='antenna diode body not on declared ground supply'))
            for key in ('area','perim'):
                if key not in params or F(params[key])<=0:
                    failures.append(dict(model=model,count=count,reason='missing/nonpositive diode parameter',parameter=key))
        else:failures.append(dict(model=model,count=count,reason='unreviewed primitive model'))
    if not models:raise ValueError('no extracted devices')
    return dict(primitive_instances=sum(models.values()),mos_instances=mos,antenna_diodes=diodes,
                models=dict(models),failures=failures,power_bulk_topology_and_parameter_signs_pass=not failures,
                supply_assumption='VPWR and VPB externally tied to ideal 1.8 V; VGND and VNB externally tied to ideal 0 V.',
                voltage_stress_and_dynamic_electrical_rules_qualified=False,
                absolute_device_geometry_qualified=False)


def run(extraction,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=extraction/'native_assessment.json';r=json.loads(receipt.read_text())
    source=extraction/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if r['artifacts'].get(str(source))!=sha(source):raise ValueError('assembled extraction changed')
    paths=[receipt,source,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        result=check(devices(subcircuits(source.read_text()),'IntegerPLL_400MHz_PrototypeTop'))
    detail=output/'topology.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         power_bulk_topology_and_parameter_signs_pass=result['power_bulk_topology_and_parameter_signs_pass'],
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Power/bulk topology and parameter signs:',result['power_bulk_topology_and_parameter_signs_pass'],
          'primitive devices:',result['primitive_instances'],'findings:',len(result['failures']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extraction',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.extraction.resolve(),a.output.resolve())
