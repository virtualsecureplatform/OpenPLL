#!/usr/bin/env python3
"""Place the prototype's three macros and audit every logical/PG connection.

This produces an unrouted assembly frame, not physical signoff or lock evidence.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT, sha, save, verify
import time,os
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/prototype400'))
sys.path.insert(0, str(ROOT/'verification/timing400'))
from check_compact_mapping import TECH, LEF, OPENROAD

DCO = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'


from build_assembly_frame import expected
def digital_views(route,checks,candidate):
    rr=route/'assessment.json';pr=checks/'assessment.json';cr=candidate/'assessment.json';lr=route/'signoff/assessment.json'
    r,p,c,l=[json.loads(x.read_text()) for x in (rr,pr,cr,lr)]
    for record in (r,p,c):verify(record['artifacts'])
    verify(l['sha256'])
    if r['candidate_source_sha256']!=c['candidate_source_sha256'] or not p['all_transition_and_output_functions_equivalent'] or p['input_sha256'].get(str(route/'route.v'))!=sha(route/'route.v'):
        raise ValueError('exact candidate route/equivalence binding required')
    if not l['diagnostic_physical_pass'] or not l['lvs_unique_match'] or l['magic_drc_rectangles'] or l['antenna_net_violations']:raise ValueError('digital child physical checks incomplete')
    lef=route/'digital.lef';gds=route/'signoff/route.gds'
    if r['artifacts'].get(str(lef))!=sha(lef) or l['sha256'].get(str(gds))!=sha(gds):raise ValueError('digital physical views changed')
    return dict(lef=str(lef),gds=str(gds),master='IntegerPLL_ProgrammedCore',evidence_sha256={str(x):sha(x) for x in (rr,pr,cr,lr)},candidate_sources=c['candidate_source_sha256'])



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--digital-route', required=True, type=Path)
    parser.add_argument('--digital-checks', required=True, type=Path)
    parser.add_argument('--candidate',required=True,type=Path)
    parser.add_argument('--dco-candidate',required=True,type=Path)
    a=parser.parse_args(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    selected=digital_views(a.digital_route.resolve(),a.digital_checks.resolve(),a.candidate.resolve())
    TOP=a.candidate.resolve()/'rtl/IntegerPLL_400MHz_PrototypeTop.v'
    candidate_sources=selected['candidate_sources'];verify(candidate_sources)
    dcor=a.dco_candidate.resolve()/'assessment.json';dc=json.loads(dcor.read_text());verify(dc['artifacts'])
    receipt=a.digital_checks.resolve()/'assessment.json'
    digital=Path(selected['lef'])
    lefs=[Path(name) for name in dc['artifacts'] if name.endswith('.lef')]
    gdss=[Path(name) for name in dc['artifacts'] if name.endswith('.gds')]
    if len(lefs)!=1 or len(gdss)!=1:raise ValueError('unique DCO physical views required')
    dco=lefs[0]
    bbpd=ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef'
    macro_sources=dict(digital={k:selected[k] for k in ('lef','gds','master')},
        oscillator=dict(lef=str(dco),gds=str(gdss[0]),master=DCO),
        detector=dict(lef=str(bbpd),gds=str(ROOT/'build/timing400/release_001/bbpd_internal_antenna_001/signoff/route.gds'),master='IntegerPLL_BBPD'))
    pins=dict(candidate_sources,**selected['evidence_sha256']);pins[str(dcor)]=sha(dcor)
    for path in (Path(__file__).resolve(),ROOT/'verification/signoff400/common_v3.py',
                 Path(OPENROAD),Path('/usr/bin/iverilog'),TECH,LEF,digital,dco,bbpd,receipt,
                 Path(selected['gds']),ROOT/'verification/prototype400/candidate_macro.py',ROOT/'verification/prototype400/build_assembly_frame.py'):
        pins[str(path)]=sha(path)
    for view in macro_sources.values():
        for role in ('lef','gds'): pins[view[role]]=sha(Path(view[role]))
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=600))
    # Preprocess the exact logical top, then add only the physical digital PG ports.
    subprocess.run(['/usr/bin/iverilog','-g2012','-E','-DUSE_POWER_PINS','-o',
                    str(out/'logical_top.v'),str(TOP)],check=True,timeout=30)
    text=(out/'logical_top.v').read_text()
    token='IntegerPLL_ProgrammedCore digital ('
    assert text.count(token)==1
    (out/'physical_top.v').write_text(text.replace(token,token+'\n        .VDD(VPWR),.VSS(VGND),'))
    tcl='\n'.join(f'read_lef {{{p}}}' for p in (TECH,LEF,digital,dco,bbpd))
    tcl+=f'''
read_verilog {{{out/'physical_top.v'}}}
link_design IntegerPLL_400MHz_PrototypeTop
initialize_floorplan -site unit -die_area {{0 0 650 500}} -core_area {{10 10 640 490}}
place_macro -macro_name digital -location {{50 100}} -orientation R0 -exact
place_macro -macro_name oscillator -location {{450 100}} -orientation R0 -exact
place_macro -macro_name detector -location {{450 300}} -orientation R0 -exact
set block [ord::get_db_block]
foreach rail {{VPWR VPB}} {{[$block findNet $rail] setSigType POWER}}
foreach rail {{VGND VNB}} {{[$block findNet $rail] setSigType GROUND}}
set f [open {{{out/'connections.tsv'}}} w]
foreach inst [$block getInsts] {{
 set bb [$inst getBBox]
 puts $f [join [list INST [$inst getName] [[$inst getMaster] getName] [$bb xMin] [$bb yMin] [$bb xMax] [$bb yMax]] "\\t"]
 foreach pin [$inst getITerms] {{
  set net [$pin getNet]
  if {{$net == "NULL"}} {{error "unconnected macro pin"}}
  puts $f [join [list PIN [$inst getName] [[$pin getMTerm] getName] [$net getName]] "\\t"]
 }}
}}
close $f
write_db {{{out/'floorplan.odb'}}}
write_def {{{out/'floorplan.def'}}}
'''
    (out/'floorplan.tcl').write_text(tcl)
    verify(pins)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(GOMAXPROCS='4',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    with lease(4,8,deadline):execute([OPENROAD,'-exit',out/'floorplan.tcl'],out/'floorplan.log',deadline,8)
    actual={}; boxes={}; masters={}
    for line in (out/'connections.tsv').read_text().splitlines():
        fields=line.split('\t')
        if fields[0]=='PIN':
            key=tuple(fields[1:3]); assert key not in actual
            actual[key]=fields[3]
        else:
            assert fields[0]=='INST'
            masters[fields[1]]=fields[2]; boxes[fields[1]]=list(map(int,fields[3:]))
    assert masters==dict(digital='IntegerPLL_ProgrammedCore',oscillator=DCO,detector='IntegerPLL_BBPD')
    want=expected()
    assert actual==want, dict(missing=list(want.keys()-actual.keys()),extra=list(actual.keys()-want.keys()),
                             wrong=[(k,v,actual.get(k)) for k,v in want.items() if actual.get(k)!=v])
    for name,b in boxes.items():
        assert 0<=b[0]<b[2]<=650000 and 0<=b[1]<b[3]<=500000, (name,b)
    names=list(boxes)
    for i,name in enumerate(names):
        for other in names[i+1:]:
            x,y=boxes[name],boxes[other]
            assert x[2]<=y[0] or y[2]<=x[0] or x[3]<=y[1] or y[3]<=x[1]
    negatives={}
    for key,value in [(('detector','RESET_N'),'osc_reset_n'),
                      (('oscillator','DCO_THERM[0]'),'fine_therm[254]'),
                      (('digital','VDD'),'VGND')]:
        corrupted=dict(actual); corrupted[key]=value
        assert corrupted!=want
        negatives['/'.join(key)]=True
    verify(pins)
    save(out/'assessment.json',dict(completed_utc=datetime.now(timezone.utc).isoformat(),
         input_sha256=pins, macro_sources=macro_sources, macro_bboxes_dbu=boxes,macro_pins_checked=len(actual),
         candidate_source_sha256=candidate_sources,DCO_selection_provisional=True,release_ready=False,
         parent_floorplan_profile='compact_650x500_v1',parent_die_area_um=[0,0,650,500],
         exact_logical_and_pg_pin_mapping_pass=True,inside_die_and_no_macro_overlap=True,
         corrupted_connections_rejected=negatives,assembly_frame_pass=True,
         physical_power_connectivity_verified=False,signal_routing_complete=False,
         extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(dict(assembly_frame_pass=True,macro_pins_checked=len(actual))))


if __name__=='__main__':main()
