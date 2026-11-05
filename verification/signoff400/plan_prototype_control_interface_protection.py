"""Cover every exposed thermal-control input while retaining proven repairs.

This is a design coverage plan, not an antenna-pass report or defect count.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from common_v3 import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/prototype400'))
from build_assembly_frame import expected

def run(frame,power,prior,output):
    receipts=[p/'assessment.json' for p in (frame,power,prior)]
    f,p,b=[json.loads(path.read_text()) for path in receipts]
    for record in (f,p,b):verify(record['input_sha256']);verify(record['artifacts'])
    if not f['assembly_frame_pass'] or not p['main_rail_database_connectivity_pass'] or not b['control_buffer_composition_proved']:
        raise ValueError('checked frame, diode power and retained buffer proof required')
    if p['candidate_source_sha256']!=f['candidate_source_sha256'] or b['candidate_source_sha256']!=f['candidate_source_sha256'] or b['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('one exact original parent source bank required')
    diode_plan=power/'placement_plan.json';prior_plan=prior/'placement_plan.json'
    diodes={row['net'] for row in json.loads(diode_plan.read_text())};retained={row['net']:row for row in json.loads(prior_plan.read_text())}
    controls={pin:net for (instance,pin),net in expected().items() if instance=='oscillator' and (pin.startswith('DCO_THERM[') or pin.startswith('COARSETHERMAL_CODE['))}
    if len(controls)!=302 or len(set(controls.values()))!=302:raise ValueError('exact 255 fine and 47 coarse control interface required')
    target_nets=set(controls.values())-diodes
    if not set(retained)<=target_nets:raise ValueError('retained buffer repairs must remain in coverage plan')
    lef=Path(f['macro_sources']['oscillator']['lef']);text=lef.read_text();x,y,_,_=f['macro_bboxes_dbu']['oscillator']
    records=[]
    for pin,net in sorted(controls.items()):
        if net not in target_nets:continue
        match=re.search(r'^\s*PIN '+re.escape(pin)+r'\s*$(.*?)^\s*END '+re.escape(pin)+r'\s*$',text,re.M|re.S)
        if match is None or not re.search(r'\bDIRECTION\s+INPUT\s*;',match[1]):raise ValueError('explicit physical input port required')
        options=[];layer=None
        for line in match[1].splitlines():
            fields=line.split()
            if fields and fields[0]=='LAYER':layer=fields[1]
            if fields and fields[0]=='RECT' and re.fullmatch(r'met[1-5]',layer or ''):
                a,bb,c,d=[Decimal(v)*1000 for v in fields[1:5]]
                options.append(dict(instance='oscillator',pin=pin,net=net,layer='m'+layer[-1],point=[int((a+c)/2)+x,int((bb+d)/2)+y]))
        if not options:raise ValueError('physical port geometry missing')
        if net in retained:
            port=retained[net]['port']
            if port not in options:raise ValueError('retained physical port shape differs')
        else:port=options[0]
        records.append(dict(net=net,macro_ports=[port],repair_target_reason='retain_proven_buffer' if net in retained else 'unprotected_control_interface_input'))
    if set(controls.values())!=(diodes&set(controls.values()))|target_nets:raise ValueError('incomplete control protection plan')
    pins={str(path):sha(path) for path in (*receipts,diode_plan,prior_plan,lef,Path(__file__).resolve())};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'records.json';save(detail,records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         record_semantics='interface_protection_design_targets_not_current_failure_count',
         total_control_inputs=302,existing_diode_protected_controls=len(diodes&set(controls.values())),
         retained_buffer_controls=len(retained),additional_buffer_controls=len(target_nets-set(retained)),
         planned_buffer_controls=len(target_nets),all_control_inputs_have_planned_protection=True,
         violations=len(records),violations_with_macro_port=len(records),
         physical_antenna_closure_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('frame','power','prior','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('frame','power','prior','output')))
