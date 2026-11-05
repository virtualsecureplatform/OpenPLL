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
from common import ROOT, TOP, source_pins, sha, save, verify
sys.path.insert(0, str(ROOT/'verification/timing400'))
from check_compact_mapping import TECH, LEF, OPENROAD

DCO = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'


from build_assembly_frame import expected
from candidate_macro import digital_views


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--digital-route', required=True, type=Path)
    parser.add_argument('--digital-checks', required=True, type=Path)
    parser.add_argument('--placement', required=True, type=Path)
    a=parser.parse_args(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    selected=digital_views(a.digital_route,a.digital_checks,a.placement)
    receipt=a.digital_checks.resolve()/'assessment.json'
    digital=Path(selected['lef'])
    dco=ROOT/f'openlane/{DCO}/runs/c1fine_range_001/final/lef/{DCO}.lef'
    bbpd=ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef'
    macro_sources=dict(digital={k:selected[k] for k in ('lef','gds','master')},
        oscillator=dict(lef=str(dco),gds=str(dco.parents[1]/'gds'/f'{DCO}.gds'),master=DCO),
        detector=dict(lef=str(bbpd),gds=str(ROOT/'build/timing400/release_001/bbpd_internal_antenna_001/signoff/route.gds'),master='IntegerPLL_BBPD'))
    pins=dict(source_pins(),**selected['evidence_sha256'])
    for path in (Path(__file__).resolve(),Path(__file__).with_name('common.py'),
                 Path(OPENROAD),Path('/usr/bin/iverilog'),TECH,LEF,digital,dco,bbpd,receipt,
                 Path(selected['gds']),Path(__file__).with_name('candidate_macro.py'),Path(__file__).with_name('build_assembly_frame.py')):
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
initialize_floorplan -site unit -die_area {{0 0 1000 850}} -core_area {{10 10 990 840}}
place_macro -macro_name digital -location {{150 150}} -orientation R0 -exact
place_macro -macro_name oscillator -location {{750 150}} -orientation R0 -exact
place_macro -macro_name detector -location {{750 400}} -orientation R0 -exact
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
    with (out/'floorplan.log').open('x') as log:
        subprocess.run([OPENROAD,'-exit',str(out/'floorplan.tcl')],stdout=log,
                       stderr=subprocess.STDOUT,check=True,timeout=540)
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
        assert 0<=b[0]<b[2]<=1000000 and 0<=b[1]<b[3]<=850000, (name,b)
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
         exact_logical_and_pg_pin_mapping_pass=True,inside_die_and_no_macro_overlap=True,
         corrupted_connections_rejected=negatives,assembly_frame_pass=True,
         physical_power_connectivity_verified=False,signal_routing_complete=False,
         extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(dict(assembly_frame_pass=True,macro_pins_checked=len(actual))))


if __name__=='__main__':main()
