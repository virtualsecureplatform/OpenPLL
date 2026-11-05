#!/usr/bin/env python3
"""Classify the eight corner model-name differences without aliasing models.

Installed Magic orig maps scnfet directly to nfet_01v8, while wrapper styles
select special_nfet_01v8 below 0.42um. Check all other native fields unchanged
and the installed special model's actual 0.36um bin. No electrical equivalence,
model substitution or nominal-netlist adoption follows from this audit.
"""
from decimal import Decimal
import json
from pathlib import Path
import re
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    comparison=base/'poly_metal_full_capacitance_corner_comparison_002'
    receipt=verify(comparison/'assessment.json')
    assert not receipt['normalized_device_statements_all_preserved']
    differences=json.loads((comparison/'normalized_device_differences.json').read_text())
    tech=ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    text=tech.read_text()
    assert 'device mosfet sky130_fd_pr__nfet_01v8 scnfet,nfet' in text
    assert re.search(r'device msubcircuit sky130_fd_pr__special_nfet_01v8 scnfet\s*\\\n.*?\\\n\s*w<0.42',text)
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')
    model=pdk/'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__special_nfet_01v8.pm3.spice'
    mtext=model.read_text()
    assert '.subckt  sky130_fd_pr__special_nfet_01v8 d g s b' in mtext
    bins=[{k:Decimal(v) for k,v in re.findall(r'\b(lmin|lmax|wmin|wmax)\s*=\s*([^\s]+)',line)} for line in mtext.splitlines() if 'lmin' in line]
    assert bins and all(len(b)==4 for b in bins)
    records={}
    for corner in ['min','max']:
        diff=differences[corner]
        assert diff['removed']==diff['added']==8
        old={tuple(row[3:]):row for row in diff['removed_examples']}
        new={tuple(row[3:]):row for row in diff['added_examples']}
        assert len(old)==len(new)==8 and old.keys()==new.keys()
        details=[]
        for key in sorted(old):
            a,b=old[key],new[key]
            assert a[2]=='sky130_fd_pr__nfet_01v8' and b[2]=='sky130_fd_pr__special_nfet_01v8'
            assert a[:2]==b[:2] and a[3:]==b[3:]
            # Native layout length/width use 0.005um extraction units.
            l,w=Decimal(a[7])*Decimal('5e-9'),Decimal(a[8])*Decimal('5e-9')
            assert l==Decimal('0.15e-6') and w==Decimal('0.36e-6')
            matching=[b for b in bins if b['lmin']<=l<=b['lmax'] and b['wmin']<=w<=b['wmax']]
            assert len(matching)==1
            bin_values=matching[0]
            details.append(dict(seed_native_coordinates=a[3:7],length_um=str(l*Decimal('1e6')),
                width_um=str(w*Decimal('1e6')),old_model=a[2],wrapper_model=b[2],all_other_fields_unchanged=True))
        records[corner]=details
    assert records['min']==records['max']
    out=base/'corner_model_name_difference_audit_001';out.mkdir(exist_ok=False)
    save(out/'differences.json',records)
    paths=[Path(__file__).resolve(),comparison/'assessment.json',comparison/'normalized_device_differences.json',tech,model]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'differences.json'):sha(out/'differences.json')},model_name_differences_per_corner=8,
        all_other_native_device_fields_preserved=True,min_max_differences_identical=True,
        explained_by_installed_magic_width_dependent_wrapper_selection=True,
        special_model_has_matching_length_width_bin=True,special_model_bin_si={k:str(v) for k,v in bin_values.items()},
        ordinary_and_special_models_are_aliased=False,electrical_equivalence_asserted=False,
        nominal_wrapper_model_scope_requires_validation=True,nominal_netlist_adopted=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    print('Eight width-selected special NFET names explained in each corner; all other fields agree. No model alias or electrical equivalence adopted.')


if __name__=='__main__':main()
