"""Inventory supplied-library load sensitivity; this is not native Cin qualification."""
import argparse
import json
import math
from pathlib import Path
import re
from common_v3 import ROOT,save,sha,verify

def pin_caps(text):
    result={}
    for block in re.split(r'\n cell \(',text)[1:]:
        master=block.split(')',1)[0]
        for match in re.finditer(r'pin\s*\(([^)]+)\)\s*\{\s*direction\s*:\s*input\s*;\s*capacitance\s*:\s*([0-9.eE+-]+)\s*;',block):
            key=(master,match[1]);value=float(match[2])
            if key in result or not math.isfinite(value) or value<0:raise ValueError('invalid native input capacitance')
            result[key]=value
    if not result:raise ValueError('native pin capacitance inventory missing')
    return result

def run(views,output):
    receipt=views/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    common=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/timing/sky130_fd_sc_hs__common.lib.json'
    if json.loads(common.read_text())['comp_attribute,capacitive_load_unit']!=[1,'pf']:
        raise ValueError('explicit supplied capacitance units required')
    pins={str(p):sha(p) for p in (receipt,common,Path(__file__).resolve())};native=None
    for corner in ('tt','ff','ss','sf','fs'):
        for edge in ('early','late'):
            path=views/f'{corner}_{edge}.lib';found=pin_caps(path.read_text())
            if native is None:native=found
            elif native!=found:raise ValueError('original native input-capacitance assumptions differ across views')
            pins[str(path)]=sha(path)
    records=[];conditional=[];base=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells'
    for (master,pin),assumed in sorted(native.items()):
        family=master.split('__')[1].rsplit('_',1)[0]
        if family=='diode':
            conditional.append(dict(master=master,pin=pin,assumed_capacitance_pf=assumed,provided_PVT_envelope_available=False));continue
        observations=[]
        for path in sorted((base/family).glob(master+'__*.lib.json')):
            data=json.loads(path.read_text());properties=data.get('pin,'+pin)
            if not isinstance(properties,dict) or properties.get('direction')!='input':continue
            values={key:float(properties[key]) for key in ('capacitance','rise_capacitance','fall_capacitance') if key in properties}
            if not values or any(not math.isfinite(v) or v<=0 for v in values.values()):raise ValueError('positive scalar supplied capacitance required')
            observations.append(dict(source=str(path),minimum_pf=min(values.values()),maximum_pf=max(values.values()),supplied_values_pf=values))
            pins[str(path)]=sha(path)
        if not observations or assumed<=0:raise ValueError('supplied PVT input capacitance inventory missing')
        low=min(row['minimum_pf'] for row in observations);high=max(row['maximum_pf'] for row in observations)
        records.append(dict(master=master,pin=pin,native_assumed_TT_capacitance_pf=assumed,
             supplied_minimum_pf=low,supplied_maximum_pf=high,minimum_ratio_to_native=low/assumed,
             maximum_ratio_to_native=high/assumed,observations=observations))
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'pin_capacitances.json';save(detail,dict(pins=records,conditional_diodes=conditional))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         supplied_input_pins_reviewed=len(records),conditional_diode_pins=len(conditional),
         global_minimum_ratio_to_native=min(r['minimum_ratio_to_native'] for r in records),
         global_maximum_ratio_to_native=max(r['maximum_ratio_to_native'] for r in records),
         operating_conditions_from_all_supplied_libraries_included=True,
         screening_envelope_only=True,native_nominal_PVT_capacitance_qualified=False,
         diode_PVT_capacitance_envelope_qualified=False,routed_load_sensitivity_screen_complete=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('views','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.views.resolve(),args.output.resolve())
