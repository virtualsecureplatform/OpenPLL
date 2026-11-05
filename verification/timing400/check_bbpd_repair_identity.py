#!/usr/bin/env python3
"""Prove functional cell/pin identity after physical-only detector protection.

Exact functional structure is preserved, including both flip-flops. This
does not prove analog timing under the changed input/supply capacitances.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from characterize_compact_propagation import PDK
from run_dco_qualification import ROOT,sha,save


def section(path,name):
    found=re.search(r'^'+name+r' \d+ ;\n(.*?)^END '+name+r'\s*$',path.read_text(),re.M|re.S)
    assert found,name
    return found[1]


def design(path):
    cells={name:(master,' '.join(body.split())) for name,master,body in re.findall(
        r'^\s*-\s+(\S+)\s+(\S+)\s+(.*?);',section(path,'COMPONENTS'),re.M|re.S)}
    pins={}
    nets={}
    for name,body in re.findall(r'^\s*-\s+(\S+)\s+(.*?);',section(path,'NETS'),re.M|re.S):
        nets[name]=' '.join(body.split())
        for inst,pin in re.findall(r'\(\s*(\S+)\s+(\S+)\s*\)',body.split('+',1)[0]):
            key=(inst,pin);assert key not in pins
            pins[key]=name
    return cells,pins,nets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();route=args.route.resolve()
    verify(route/'assessment.json')
    source=ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/def/IntegerPLL_BBPD.def'
    original,oldpins,oldnets=design(source)
    revised,newpins,newnets=design(route/'route.def')
    removed={'FILLER_16_85','FILLER_18_85'}
    added={f'antenna_{net}_{kind}' for net in ('REF','CLKDIVR') for kind in ('decap_6','decap_4','diode_2')}
    assert set(original)-set(revised)==removed and set(revised)-set(original)==added
    assert all(original[n]==revised[n] for n in set(original)&set(revised))
    assert section(source,'PINS')==section(route/'route.def','PINS')
    lef=PDK/'libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef'
    text=lef.read_text();physical=set()
    for name,body in re.findall(r'^MACRO (\S+)\s*\n(.*?)^END \1\s*$',text,re.M|re.S):
        masterpins=re.findall(r'\bPIN\s+(\S+)\s*\n(.*?)\n\s*END\s+\1',body,re.S)
        if masterpins and all(re.search(r'\bUSE (POWER|GROUND)\s*;',p) for _,p in masterpins):physical.add(name)
    for name in removed:assert original[name][0] in physical
    functional={n:row for n,row in original.items() if row[0] not in physical}
    assert len(functional)==13
    # Source DEF keeps rail endpoints only in SPECIALNETS; OpenROAD also
    # writes regular POWER/GROUND records after explicit PG attachment.
    def signal_bindings(pins):
        return {k:v for k,v in pins.items()
                if (k[0]=='PIN' or k[0] in functional)
                and k[1] not in {'VPWR','VGND','VPB','VNB'}}
    expected=signal_bindings(oldpins)

    def validate(pins):
        actual=signal_bindings(pins)
        assert actual==expected
        for net in ('REF','CLKDIVR'):
            assert pins[f'antenna_{net}_diode_2','DIODE']==net

    validate(newpins)
    negative=[]
    for label,key,value in [('wrong_diode_net',('antenna_CLKDIVR_diode_2','DIODE'),'REF'),
                           ('swapped_clock',('direction_ff','CLK'),'CLKDIVR')]:
        corrupted=copy.deepcopy(newpins);corrupted[key]=value
        try:validate(corrupted)
        except AssertionError:negative.append(label)
        else:raise AssertionError('negative accepted: '+label)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__).resolve(),route/'assessment.json',route/'route.def',source,lef]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        exact_functional_cell_pin_binding_identity=True,functional_cells_unchanged=13,
        state_primitives_unchanged=2,all_retained_placement_records_identical=True,
        all_macro_pin_shapes_and_locations_identical=True,added_protection_inputs_correct=True,
        negative_controls_rejected=negative,
        changed_existing_routed_net_records=[n for n in oldnets if n in newnets and oldnets[n]!=newnets[n]],
        passive_load_and_supply_capacitance_effects_excluded=True,
        analog_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('All13functionalcell bindings, bothFFs andports identical; two bad-clock/diode controls rejected.')


if __name__=='__main__':main()
