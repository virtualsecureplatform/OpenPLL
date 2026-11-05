#!/usr/bin/env python3
"""Bind every repaired-assembly native antenna gate to an independent component.

Reconstruct only the two failing formation stages, probe the exact native
MOS gate points, and require a one-to-one match with all independent violating
components. This is spatial/topological cross-validation, not validation of
all foundry rules or analog effects. Drawn sidewall perimeter can numerically
differ from Magic contact-edge accounting; record those numerical differences.
"""
import argparse
import json
from pathlib import Path
import sys
import pya
from check_forming_antenna_geometry import geometry,STAGES
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--geometry',required=True,type=Path)
    parser.add_argument('--localization',required=True,type=Path)
    parser.add_argument('--stream',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    independent=args.geometry.resolve()
    localized=args.localization.resolve()
    verify(independent/'assessment.json');verify(localized/'assessment.json')
    native=json.loads((localized/'debug_records.json').read_text())
    records=json.loads((independent/'components.json').read_text())
    total=len(native)
    assert total>0 and all(r['exact_gate_match'] for r in native)
    violating={(r['stage'],r['cluster']):r for r in records if r['violation']}
    assert len(violating)==total
    source=args.stream.resolve()/'assembly.gds'
    verify(args.stream.resolve()/'assessment.json')
    layout=pya.Layout();layout.read(str(source));geom=geometry(layout,layout.cell('IntegerPLL_400MHz_CandidateTop'))
    matches=[];seen=set()
    for stage in sorted({r['stage'] for r in violating.values()}):
        selected=['gate','diff','tap']+STAGES[:STAGES.index(stage)+1]
        regs={k:geom[k].dup() for k in selected};engine=pya.LayoutToNetlist('FLAT',.001)
        for name,reg in regs.items():engine.register(reg,name);engine.connect(reg)
        engine.connect(regs['gate'],regs['poly'])
        for key in ['poly','diff','tap','li']:engine.connect(regs[key],regs['licon'])
        for a,b in [('li','mcon'),('mcon','m1')]+[(a,b) for i in range(1,5) for a,b in [(f'm{i}',f'v{i}'),(f'v{i}',f'm{i+1}')]]:
            if a in regs and b in regs:engine.connect(regs[a],regs[b])
        engine.extract_netlist()
        for index,row in enumerate(native):
            if row['plane']!='metal'+stage[1:]:continue
            x0,y0,x1,y1=row['gate_box_internal_units']
            point=pya.Point((x0+x1)*5//2,(y0+y1)*5//2)
            net=engine.probe_net(regs['gate'],point);assert net is not None
            key=(stage,net.cluster_id);assert key in violating and key not in seen
            gate=engine.shapes_of_net(net,regs['gate'],True).merged()
            record=violating[key]
            assert gate.area()*1e-6==record['gate_area_um2']
            assert [str(v) for v in [gate.bbox().left,gate.bbox().bottom,gate.bbox().right,gate.bbox().top]]==record['gate_bbox_nm']
            normalized=record['ratio']/record['allowed_ratio']*row['display_limit']
            # Both methods independently flag this component. Numerical
            # perimeter accounting differs; retain differences without
            # treating either method as a certified bound.
            assert record['violation']
            seen.add(key);matches.append(dict(native_record=index,stage=stage,cluster=net.cluster_id,
                native_display_ratio=row['effective_ratio'],independent_normalized_ratio=normalized,
                relative_difference=normalized/row['effective_ratio']-1))
        print(stage,'all native gate points bound to distinct independent violating components',flush=True)
    assert seen==set(violating)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('check_forming_antenna_geometry.py'),Path(sys.executable),source,
           independent/'assessment.json',independent/'components.json',localized/'assessment.json',localized/'debug_records.json',
           base/'forming_antenna_geometry_controls_001/assessment.json']
    verify(paths[-1])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'matches.json',matches)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(out/'matches.json'):sha(out/'matches.json')},
        native_violations_spatially_bound=total,independent_violating_components_matched=total,
        no_unmatched_violating_components=True,no_native_violations_unmatched=True,
        all_matched_components_fail_both_checks=True,
        numerical_ratio_bounds_qualified=False,
        min_relative_ratio_difference=min(r['relative_difference'] for r in matches),
        max_relative_ratio_difference=max(r['relative_difference'] for r in matches),
        fabrication_rule_coverage_qualified=False,antenna_qualified=False,release_qualified=False,scope=__doc__))

if __name__=='__main__':main()
