#!/usr/bin/env python3
"""Bind the two-geometry translator to actual instances and checked native models.

Verify HD/HS evidence, all actual726 wrapper geometries and fifteen fixed-T
model renderings against the models used by the completed HS native runs.
Reject unknown geometry, duplicate/continued cards, global scaling and reuse.
This prepares diode-compatible fragments; no physical PLL model is adopted.
"""
import json
from pathlib import Path
import sys
from run_dco_qualification import ROOT,save
sys.path.insert(0,str(ROOT/'scripts'))
from translate_sky130_checked_diode_geometries import qualification,render,translate,digest,DEVICE


def model_lines(text):
    return [s.strip() for s in text.splitlines() if s.startswith('.model openpll_pw2nd_candidate ') or s.startswith('+ ')]


def main():
    base=ROOT/'build/timing400/release_001'
    hd=ROOT/'build/modern_25mhz/diode_qualification_ng47.json'
    hs=base/'hs_diode_geometry_comparison_001/assessment.json'
    electrical=ROOT/'build/modern_25mhz/diode_translation_grid_ng47_v2/summary.json'
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')
    parameters,evidence,model=qualification(hd,hs,electrical,pdk)
    extraction=base/'poly_metal_full_capacitance_corners_002/min'
    native=json.loads((extraction/'native_completion.json').read_text())
    source=extraction/'capacitance.spice'
    assert digest(source)==native['artifacts'][str(source)]
    actual=[]
    with source.open() as stream:
        for line in stream:
            if line.startswith('C'):break
            if line.startswith('X') and DEVICE in line:actual.append(line.strip())
    assert len(actual)==726
    fixture='* Actual extracted full-layout diode wrapper cards; no full PLL adoption.\n'+'\n'.join(actual)+'\n'
    _,counts=translate(fixture);assert counts=={'hs':724,'hd':2} or counts=={'hd':2,'hs':724}
    out=base/'checked_diode_geometry_translation_controls_001';out.mkdir(exist_ok=False)
    include=out/'actual_diode_wrappers.spice';include.write_text(fixture)
    checked=[];paths=[Path(__file__).resolve(),ROOT/'scripts/translate_sky130_checked_diode_geometries.py',
        ROOT/'scripts/sky130_diode_translation_probe.py',hd,hs,electrical,model,source,extraction/'native_completion.json']
    for corner in ['tt','ff','ss','sf','fs']:
        for temperature in [-40,27,125]:
            text,counts=render(fixture,temperature,parameters[corner])
            assert counts=={'hs':724,'hd':2} or counts=={'hd':2,'hs':724}
            native_deck=base/f'hs_diode_geometry_comparison_001/electrical/{corner}_{temperature}C/xyce_dc.cir'
            assert model_lines(text)==model_lines(native_deck.read_text())
            new_instances=[s.split() for s in text.splitlines() if s.startswith('X')]
            assert len(new_instances)==726
            assert all(a.split()[:3]==b[:3] and len(b)==4 for a,b in zip(actual,new_instances))
            target=out/f'{corner}_{temperature}C.spice';target.write_text(text)
            paths.append(native_deck);checked.append(dict(corner=corner,temperature_c=temperature,HD_instances=2,HS_instances=724,
                density_model_matches_completed_native_HS_run=True,all_native_instance_names_and_node_order_preserved=True))
    hs_card=next(s for s in actual if '6.417e+11' in s or '6.417e11' in s or '641700000000' in s)
    fields=hs_card.split();unknown=' '.join(fields[:4]+['area=6.417e11','perim=3.25e6'])
    controls={'unknown_geometry':unknown,'duplicate_parameter':hs_card+' area=6.417e11',
        'continued_instance':' '.join(fields[:-1])+'\n+ '+fields[-1],
        'global_scale':'.option scale=1e-6\n'+fixture,'complete_deck':fixture+'\n.end\n',
        'already_translated':render(fixture,27,parameters['tt'])[0]}
    rejected=[]
    for name,text in controls.items():
        try:translate(text)
        except ValueError:rejected.append(name)
        else:raise AssertionError('fault accepted: '+name)
    save(out/'model_checks.json',checked)
    save(out/'assessment.json',dict(input_sha256={str(p):digest(p) for p in paths},
        qualification_evidence_sha256=evidence,
        artifacts={str(p):digest(p) for p in out.iterdir() if p.is_file()},
        actual_native_diode_cards=726,HD_checked_geometry_instances=2,HS_checked_geometry_instances=724,
        fixed_temperature_corner_models_checked=15,all_density_models_identical_to_completed_HS_native_models=True,
        instance_names_and_node_order_preserved=True,unknown_geometry_and_unsupported_input_controls_rejected=rejected,
        fixed_temperature_model_requires_matching_global_temperature=True,
        tested_diode_model_compatibility_support_prepared=True,
        full_physical_PLL_model_integrated=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    print('Checked translation of all726 actual wrappers:2HD+724HS,15native-matched models; unsupported inputs rejected. No full PLL model adopted.')


if __name__=='__main__':main()
