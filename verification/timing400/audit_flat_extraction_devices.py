#!/usr/bin/env python3
"""Check exported device geometry and the decap warning tally against source layouts.

A matching warning count is explanatory evidence, not a substitute for captured
per-warning feedback. The raw electrical network remains unqualified.
"""
from collections import Counter
from decimal import Decimal,localcontext
import json
from pathlib import Path
import re
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';source=base/'parent_filled_metal_capacitance_extract_002'
    n=verify(source/'native_completion.json');assert n['native_extraction_completed']
    view=base/'parent_filled_metal_capacitance_view_002/assessment.json';v=verify(view)
    native=base/'parent_dco_antenna_native_filled_011';verify(native/'native_completion.json')
    refs=[base/'compact_internal_antenna_001/route.def',base/'bbpd_internal_antenna_001/route.def',
        ROOT/'openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160/runs/c1fine_range_001/final/def/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.def']
    counts=Counter()
    for path in refs:
        cells,_,_=design(path);counts.update(master for master,body in cells.values())
    models=['sky130_fd_sc_hs__decap_4',*[f'sky130_fd_sc_hd__decap_{i}' for i in [3,4,6,8,12]]]
    warnings_per_model={}
    for model in models:
        ext=native/'extraction'/(model+'.ext');text=ext.read_text()
        assert text.count('device mosfet ')==2,model
        warnings_per_model[model]=2
    feedback=(native/'extraction_feedback.txt').read_text()
    assert feedback.count('device missing 1 terminal;')==12
    expected_warnings=sum(counts[m]*warnings_per_model[m] for m in models)
    actual_warnings=int(re.search(r'Total of (\d+) warnings\.',(source/'extract.log').read_text())[1])
    spice=source/'capacitance.spice';mos=Counter();moscaps=Counter();area=Decimal(0);resistors=[];current=None
    def assess(card):
        nonlocal area
        fields=card.split();assert fields[0][0]=='M'
        params=dict(re.findall(r'\b(w|l|m)=([^\s]+)',card));assert 'w' in params and 'l' in params
        w,l,m=[Decimal(params.get(k,'1')) for k in ['w','l','m']];assert min(w,l,m)>0
        with localcontext() as ctx:ctx.prec=40;area+=w*l*m
        d,g,s,b=fields[1:5];model=fields[5];mos[model]+=1
        if d==s and d in {'VPWR','VGND'} and b==d and g in {'VPWR','VGND'} and g!=d:moscaps[model]+=1
    with spice.open() as stream:
        for line in stream:
            if line.startswith('+') and current is not None:current+=' '+line[1:].strip();continue
            if current is not None:assess(current);current=None
            if line[:1]=='C':break
            if line[:1]=='M':current=line.strip()
            elif line[:1]=='R':
                f=line.split();r=Decimal(f[3]);assert r>0;resistors.append(dict(name=f[0],nodes=f[1:3],resistance_ohm=str(r)))
    expected_area=Decimal(v['mos_gate_area_nm2'])*Decimal('1e-6');delta=area-expected_area
    out=base/'parent_filled_extraction_device_audit_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),source/'native_completion.json',spice,source/'extract.log',view,*refs,
        native/'native_completion.json',native/'extraction_feedback.txt',*[native/'extraction'/(m+'.ext') for m in models]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        native_mos_devices_by_model=dict(mos),native_mos_devices=sum(mos.values()),exported_mos_gate_area_um2=str(area),
        manufacturing_gate_area_um2=str(expected_area),exported_minus_manufacturing_gate_area_um2=str(delta),
        exact_gate_area_conservation=delta==0,rail_decoupling_mos_devices_by_model=dict(moscaps),rail_decoupling_mos_devices=sum(moscaps.values()),
        decap_cell_counts={m:counts[m] for m in models},known_missing_terminal_warnings_per_cell=warnings_per_model,
        expected_flattened_missing_terminal_warning_count=expected_warnings,observed_flattened_warning_count=actual_warnings,
        warning_tally_matches_known_decap_instances=expected_warnings==actual_warnings,
        exported_decoupling_mos_count_matches_warning_tally=sum(moscaps.values())==actual_warnings,
        actual_full_flattened_feedback_not_captured=True,positive_native_resistor_devices=resistors,
        full_electrical_model_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Native gate area',area,'vs GDS',expected_area,'delta',delta,'um2; decap expected warnings',expected_warnings,'observed',actual_warnings,'exported MOSCAPs',sum(moscaps.values()),flush=True)

if __name__=='__main__':main()
