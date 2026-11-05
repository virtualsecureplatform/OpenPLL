#!/usr/bin/env python3
"""Stream the parent with original and targeted external diode/tap islands."""
import argparse
from itertools import combinations
import json
from pathlib import Path
import signal
import re
import subprocess
import sys

import pya

from check_compact_clock_tree import verify
from check_compact_mapping import TECH, LEF
from run_dco_qualification import ROOT, sha, save

TOP = 'IntegerPLL_400MHz_CandidateTop'
STREAM = Path('/nix/store/15gw4cny6dmil9965l9csn881g1j6lvi-python3.13-librelane-3.0.4/lib/python3.13/site-packages/librelane/scripts/klayout/stream_out.py')


def layers(layout):
    return {(layout.get_info(i).layer,layout.get_info(i).datatype):i for i in layout.layer_indices()}


def texts(cell, index):
    if index is None:
        return []
    iterator = cell.begin_shapes_rec(index)
    result = []
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_text():
            result.append(shape.text.transformed(iterator.trans()).to_s())
        iterator.next()
    return sorted(result)


def same_cell(a, acell, b, bcell):
    assert a.dbu == b.dbu
    alayers, blayers = layers(a), layers(b)
    for key in sorted(alayers.keys()|blayers.keys()):
        ai, bi = alayers.get(key), blayers.get(key)
        ar = pya.Region(acell.begin_shapes_rec(ai)) if ai is not None else pya.Region()
        br = pya.Region(bcell.begin_shapes_rec(bi)) if bi is not None else pya.Region()
        assert (ar ^ br).is_empty(), ('geometry conflict',acell.name,key)
        assert texts(acell,ai) == texts(bcell,bi), ('label conflict',acell.name,key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--route',type=Path,required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('12h stream check budget')))
    signal.alarm(43200)
    base = ROOT/'build/timing400/release_001'
    route = args.route.resolve()
    repair = verify(route/'assessment.json')
    assert repair['main_rail_connectivity_passed'] and repair['detailed_route_completed']
    assert repair['router_drc_violations']==0 and repair['parent_signal_routes_rebuilt']
    placement = base/'parent_dco_antenna_placement_002'
    verify(placement/'assessment.json')
    plan = json.loads((placement/'placement_plan.json').read_text())
    assert len(plan)==131
    extra_inputs=[]
    if 'extra_placement_plan' in repair:
        extra=Path(repair['extra_placement_plan'])
        added=json.loads(extra.read_text())
        assert len(added)==10 and all(r['diodes']==4 for r in added)
        plan+=added
        extra_inputs.append(extra)
    digital = base/'compact_internal_antenna_001/signoff'
    verify(base/'compact_internal_antenna_closure_audit_001/assessment.json')
    verify(base/'bbpd_internal_antenna_formation_001/assessment.json')
    digital_report = json.loads((digital/'assessment.json').read_text())
    assert sha(digital/'route.gds') == digital_report['sha256'][str(digital/'route.gds')]
    native = ROOT/'build/timing450/dco_c1_fine_load_001'
    dco_report = json.loads((native/'physical_160.json').read_text())
    dco = Path(dco_report['gds'])
    assert sha(dco)==dco_report['gds_sha256']
    sampled = ROOT/'build/timing450/interface_characterization/bbpd_sampled'
    bbpd_report = base/'bbpd_internal_antenna_001/signoff/assessment.json'
    sampled_report = verify(bbpd_report)
    assert sampled_report['magic_drc_rectangles']==0 and sampled_report['lvs_unique_match']
    bbpd = base/'bbpd_internal_antenna_001/signoff/route.gds'
    assert sha(bbpd)==sampled_report['sha256'][str(bbpd)]
    sources = [digital/'route.gds',dco,bbpd]
    macro_names = ['IntegerPLL_AcquiringCore',dco.stem,'IntegerPLL_BBPD']
    lefs = [base/'digital_macro_abstract_001/IntegerPLL_AcquiringCore.lef',
            dco.parent.parent/'lef'/(dco.stem+'.lef'),
            sampled/'runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef']
    pdk = ROOT/'build/timing450/pdk/sky130A'
    tech_files = [pdk/'libs.tech/klayout/tech'/('sky130A.'+ext) for ext in ('lyt','lyp','map')]
    inputs = [Path(__file__).resolve(),Path(sys.executable),STREAM,TECH,LEF,*sources,*lefs,
              *tech_files,*extra_inputs,route/'route.def',route/'assessment.json',placement/'assessment.json',placement/'placement_plan.json',
              digital/'assessment.json',native/'physical_160.json',bbpd_report,
              base/'compact_internal_antenna_closure_audit_001/assessment.json',
              base/'bbpd_internal_antenna_formation_001/assessment.json']
    pins = {str(p):sha(p) for p in inputs}
    layouts, names = [], []
    for source, top in zip(sources,macro_names):
        layout = pya.Layout();layout.read(str(source))
        assert layout.cell(top) is not None
        assert not any(c.is_ghost_cell() for c in layout.each_cell())
        layouts.append(layout);names.append({c.name for c in layout.each_cell()})
    duplicates = []
    out.mkdir(parents=True)
    for i,j in combinations(range(3),2):
        for name in sorted(names[i]&names[j]):
            same_cell(layouts[i],layouts[i].cell(name),layouts[j],layouts[j].cell(name))
            duplicates.append(dict(first=i,second=j,cell=name,geometry_and_labels_identical=True))
    save(out/'input_manifest.json',dict(input_sha256=pins,macro_names=macro_names,
        duplicate_cells=duplicates,wall_clock_budget_s=43200,release_qualified=False))
    command = [sys.executable,str(STREAM),'-o',str(out/'assembly.gds'),'-t',TOP,
               '-T',str(tech_files[0]),'-P',str(tech_files[1]),'-M',str(tech_files[2]),
               '--conflict-resolution','OverwriteCell','-l',str(TECH),'-l',str(LEF)]
    for lef in lefs:command += ['-l',str(lef)]
    for source in sources:command += ['-w',str(source)]
    command.append(str(route/'route.def'))
    with (out/'stream.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
    assembled = pya.Layout();assembled.read(str(out/'assembly.gds'))
    top = assembled.cell(TOP)
    assert top is not None and assembled.top_cells()==[top]
    assert not any(c.is_ghost_cell() for c in assembled.each_cell())
    instances = list(top.each_inst())
    expected = {macro_names[0]:(150000,150000),macro_names[1]:(750000,150000),macro_names[2]:(750000,400000)}
    macro_instances = [inst for inst in instances if inst.cell.name in expected]
    assert len(macro_instances)==3 and {inst.cell.name for inst in macro_instances}==set(expected)
    via_definitions = set()
    for path in [TECH,LEF,*lefs]:
        via_definitions.update(re.findall(r'^\s*VIA\s+(\S+)',path.read_text(),re.M))
    via_section = (route/'route.def').read_text().split('VIAS ',1)[1].split('END VIAS',1)[0]
    via_definitions.update(re.findall(r'^\s*-\s+(\S+)',via_section,re.M))
    physical_names={'sky130_fd_sc_hs__diode_2','sky130_fd_sc_hs__tapvpwrvgnd_1'}
    physical=[inst for inst in instances if inst.cell.name in physical_names]
    assert len(physical)==5*len(plan)
    wanted=[]
    for row in plan:
        assert row['orient']=='R0'
        wanted.append(('sky130_fd_sc_hs__tapvpwrvgnd_1',row['x_nm'],row['y_nm']))
        wanted.extend(('sky130_fd_sc_hs__diode_2',row['x_nm']+480+i*960,row['y_nm']) for i in range(4))
    observed=[]
    for inst in physical:
        trans=inst.cplx_trans
        assert trans.mag==1 and trans.angle==0 and not trans.is_mirror()
        assert inst.na<=1 and inst.nb<=1
        observed.append((inst.cell.name,trans.disp.x,trans.disp.y))
    assert sorted(observed)==sorted(wanted)
    for name in physical_names:same_cell(layouts[0],layouts[0].cell(name),assembled,assembled.cell(name))
    helpers = [inst for inst in instances if inst.cell.name not in expected and inst.cell.name not in physical_names]
    for inst in helpers:
        assert inst.cell.name.startswith('VIA_') and inst.cell.name[4:] in via_definitions
        assert not list(inst.cell.each_inst()) and not inst.cell.is_empty()
    for inst in macro_instances:
        transform = inst.cplx_trans
        assert transform.mag==1 and transform.angle==0 and not transform.is_mirror()
        assert inst.na<=1 and inst.nb<=1
        assert (transform.disp.x,transform.disp.y)==expected[inst.cell.name]
    for layout,name in zip(layouts,macro_names):
        same_cell(layout,layout.cell(name),assembled,assembled.cell(name))
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        top=TOP,macro_instances=3,duplicate_cells_checked=len(duplicates),
        via_helper_instances=len(helpers),via_helper_definitions=len({i.cell.name for i in helpers}),
        all_source_macro_geometry_and_labels_preserved=True,missing_cells=0,
        parent_diode_instances=4*len(plan),parent_well_tap_instances=len(plan),external_physical_cell_placements_match_plan=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Streamed three-macro GDS; duplicate definitions and complete source macro geometry/labels checked.')


if __name__ == '__main__':
    main()
