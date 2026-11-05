#!/usr/bin/env python3
"""Inventory all final-layout diode geometries and test existing scope guards."""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save

sys.path.insert(0,str(ROOT/'scripts'))
from translate_sky130_diode import translate


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'parent_filled_poly_metal_capacitance_extract_003'
    verify(source/'native_completion.json')
    controls=base/'primitive_corner_exports_001'
    verify(controls/'assessment.json')
    observations=json.loads((controls/'observations.json').read_text())
    expected={}
    for family in ['hs','hd']:
        record=observations['nom'][family+'_diode']['native_device_records']
        assert len(record)==1
        fields=record[0].split()
        a,p=Decimal(fields[7].split('=')[1]),Decimal(fields[8].split('=')[1])
        physical_area=a*Decimal('0.000025')
        physical_perimeter=p*Decimal('0.005')
        expected[physical_area,physical_perimeter]=observations['nom'][family+'_diode']['master']
    grouped=defaultdict(list)
    spice=source/'capacitance.spice'
    with spice.open() as stream:
        for line in stream:
            if line.startswith('C'):
                break
            if not line.startswith('D'):
                continue
            f=line.split()
            assert f[3]=='sky130_fd_pr__diode_pw2nd_05v5'
            params=dict(re.findall(r'\b(area|pj)=([^\s]+)',line))
            assert set(params)=={'area','pj'}
            a,p=Decimal(params['area']),Decimal(params['pj'])
            physical=(a*Decimal('1e-12'),p*Decimal('1e-6'))
            assert physical in expected,physical
            grouped[physical].append(dict(name=f[0],nodes=f[1:3],exported_area=str(a),exported_perimeter=str(p)))
    assert sum(map(len,grouped.values()))==726 and len(grouped)==2
    records=[]
    for (area,perimeter),instances in sorted(grouped.items()):
        sample=instances[0]
        fixture=f'Xscope A B sky130_fd_pr__diode_pw2nd_05v5 area={sample["exported_area"]} perim={sample["exported_perimeter"]}\n'
        try:
            _,count=translate(fixture)
            assert count==1
            accepted=True
        except ValueError as error:
            assert 'outside checked scope' in str(error),str(error)
            accepted=False
        records.append(dict(master=expected[area,perimeter],effective_area_um2=str(area),
            effective_perimeter_um=str(perimeter),instances=len(instances),
            extracted_area_argument=sample['exported_area'],extracted_perimeter_argument=sample['exported_perimeter'],
            accepted_by_existing_fixed_geometry_translator=accepted,instances_detail=instances))
    hd=next(r for r in records if '_hd__' in r['master'])
    hs=next(r for r in records if '_hs__' in r['master'])
    assert hd['accepted_by_existing_fixed_geometry_translator']
    assert not hs['accepted_by_existing_fixed_geometry_translator']
    out=base/'current_diode_geometry_inventory_001'
    out.mkdir(exist_ok=False)
    save(out/'geometries.json',records)
    paths=[Path(__file__).resolve(),ROOT/'scripts/translate_sky130_diode.py',source/'native_completion.json',spice,
        controls/'assessment.json',controls/'observations.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'geometries.json'):sha(out/'geometries.json')},diode_instances=726,
        effective_geometries=2,hd_instances_in_existing_geometry_scope=hd['instances'],
        hs_instances_outside_existing_geometry_scope=hs['instances'],
        existing_translator_scope_guard_correctly_rejects_hs=True,
        hs_geometry_requires_own_electrical_and_noise_comparisons=True,
        native_cad_diode_scaling_not_blindly_modified=True,native_analog_jobs_added=0,
        all_current_diode_geometries_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Inventory726 diodes:',hd['instances'],'HD in existing scope;',hs['instances'],'HS require their own geometry comparisons.')


if __name__=='__main__':
    main()
