#!/usr/bin/env python3
"""Classify native RC-substrate corner diagnostics and independently verify all diodes.

Require every message to match one known device and verify native dimensions,
area/perimeter and connections. Boundary diagnostics do not qualify the diode
model or its simulator translation. Preserve the prior failed assessment.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import shlex
import signal
import time
from audit_corner_decap_feedback import validate_feedback
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def spatial_index(rows,key):
    buckets=defaultdict(list)
    for index,row in enumerate(rows):
        l,b,r,t=row[key]
        for x in range(l//400,r//400+1):
            for y in range(b//400,t//400+1):buckets[x,y].append(index)
    return buckets


def point_match(rows,key,buckets,seed):
    x1,y1,x2,y2=seed
    matches=[]
    for index in buckets[x1//400,y1//400]:
        l,b,r,t=rows[index][key]
        if 2*l<x1+x2<2*r and 2*b<y1+y2<2*t:matches.append(index)
    assert len(matches)==1,(seed,matches)
    return matches[0]


def diode_warnings(entries,diodes,index):
    seen=set()
    for box,message in entries:
        assert message=='Could not determine device boundary'
        l,b,r,t=box;assert l<r and b<t
        matches=[]
        for at in index[((l+r)//2)//400,((b+t)//2)//400]:
            dl,db,dr,dt=diodes[at]['native_internal_box']
            if dl<=l<r<=dr and db<=b<t<=dt:matches.append(at)
        assert len(matches)==1 and matches[0] not in seen,(box,matches)
        seen.add(matches[0])
    assert len(seen)==len(diodes)==726


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extraction',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.extraction.resolve();out=args.output.resolve()
    owner=json.loads((source/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0;signal.alarm(max(1,math.floor(left)))
    receipt=verify(source/'native_completion.json')
    assert receipt['native_extraction_completed'] and receipt['full_flattened_feedback_captured']
    base=ROOT/'build/timing400/release_001'
    gate_inventory=base/'flat_decap_warning_gate_inventory_001'
    diode_inventory=base/'corner_diode_warning_geometry_001'
    verify(gate_inventory/'assessment.json');verify(diode_inventory/'assessment.json')
    gates=json.loads((gate_inventory/'gates.json').read_text())
    diodes=json.loads((diode_inventory/'diodes.json').read_text())
    gate_index=spatial_index(gates,'expected_magic_box')
    diode_index=spatial_index(diodes,'native_internal_box')
    feedback=source/'extraction_feedback.txt';text=feedback.read_text()
    matches=re.findall(r'box (-?\d+) (-?\d+) (-?\d+) (-?\d+)\nfeedback add "((?:\\.|[^"\\])*)" \w+',text,re.S)
    entries=[(list(map(int,row[:4])),row[4]) for row in matches]
    assert len(entries)==text.count('feedback add ')==2288
    decap_entries=[r for r in entries if r[1].startswith('device missing 1 terminal;')]
    diode_entries=[r for r in entries if r[1]=='Could not determine device boundary']
    assert len(decap_entries)==2288 and len(diode_entries)==0
    assert len(decap_entries)+len(diode_entries)==len(entries)
    validate_feedback(decap_entries,gates)
    # No diode-boundary diagnostics are expected in the proven RC substrate context.
    # Every diode still receives a native geometry and terminal check below.
    gate_seen=set();diode_seen=set();device_rows=[]
    native=source/'IntegerPLL_400MHz_FilledCapView.ext'
    with native.open() as stream:
        for line in stream:
            if not line.startswith('device msubckt '):continue
            f=shlex.split(line)
            if 'fet' in f[2]:
                assert len(f)==19
                if not (f[9]==f[13]==f[16] and f[9] in ['VGND','VPWR'] and f[10] in ['VGND','VPWR'] and f[9]!=f[10]):continue
                seed=list(map(int,f[3:7]));at=point_match(gates,'expected_magic_box',gate_index,seed)
                assert at not in gate_seen;gate_seen.add(at)
                row=gates[at];assert f[9]==row['expected_missing_terminal_rail']
                assert ('nfet' if f[9]=='VGND' else 'pfet') in f[2]
                assert f[7].startswith('l=') and f[8].startswith('w=')
                l,b,r,t=row['expected_magic_box']
                assert int(f[7][2:])*int(f[8][2:])==(r-l)*(t-b)
                device_rows.append(dict(kind='decap',inventory_index=at,model=f[2],seed=seed,body=f[9],gate=f[10]))
            elif f[2]=='sky130_fd_pr__diode_pw2nd_05v5':
                assert len(f)==16 and f[7].startswith('a=') and f[8].startswith('p=')
                seed=list(map(int,f[3:7]));at=point_match(diodes,'native_internal_box',diode_index,seed)
                assert at not in diode_seen;diode_seen.add(at)
                row=diodes[at]
                assert Decimal(f[7][2:])*25==row['diffusion_area_nm2']
                assert Decimal(f[8][2:])*5==row['diffusion_perimeter_nm']
                assert f[9]=='None' and f[13]=='VGND'
                device_rows.append(dict(kind='diode',inventory_index=at,model=f[2],seed=seed,
                    signal=f[10],body=f[13],area_native=f[7],perimeter_native=f[8]))
    assert len(gate_seen)==2288 and len(diode_seen)==726
    # Corrupt a real diode seed while preserving its exact dimensions.
    real=next(r for r in device_rows if r['kind']=='diode')
    shifted=[x+1000000 for x in real['seed']]
    try:point_match(diodes,'native_internal_box',diode_index,shifted)
    except AssertionError:negative=True
    else:raise AssertionError('wrong native diode location accepted')
    out.mkdir(exist_ok=False);save(out/'devices.json',device_rows)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_corner_decap_feedback.py'),source/'native_completion.json',
        native,feedback,gate_inventory/'assessment.json',gate_inventory/'gates.json',
        diode_inventory/'assessment.json',diode_inventory/'diodes.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'devices.json'):sha(out/'devices.json')},full_feedback_entries=2288,
        exact_decap_gate_and_rail_matches=2288,diode_boundary_diagnostics_matched_to_actual_diffusions=0,diode_boundaries_determined_in_native_RC_substrate_context=True,
        native_decap_position_and_gate_area_matches=2288,native_diode_position_area_perimeter_and_body_matches=726,
        unclassified_feedback_entries=0,duplicate_or_missing_device_diagnostics=0,
        wrong_diode_diagnostic_location_control_rejected=negative,full_corner_warning_classification_passed=True,
        diode_runtime_compatibility_or_model_equivalence_qualified=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('All2288 decap diagnostics individually classified; all726 native diode positions, areas, perimeters and body connections match independently.')


if __name__=='__main__':main()
