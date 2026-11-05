#!/usr/bin/env python3
"""Match corner-wrapper extraction terminal warnings to actual decap gates.

Require exact GDS gate coordinates, the correct well-derived rail, and a native
MOSCAP with matching gate area and D=S=bulk. This classifies these warnings only;
it does not qualify complete model coverage or nonlinear timing behavior.
"""
import argparse
from collections import defaultdict
import copy
import json
import math
from pathlib import Path
import re
import shlex
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def validate_feedback(entries, gates):
    expected = {tuple(row['expected_magic_box']): row for row in gates}
    seen = set()
    for box, message in entries:
        key = tuple(box)
        assert key in expected and key not in seen, ('unexpected/duplicate gate warning',box,message)
        assert message == 'device missing 1 terminal;\n connecting remainder to node '+expected[key]['expected_missing_terminal_rail'], (box,message)
        seen.add(key)
    assert seen==set(expected), ('missing warnings',len(set(expected)-seen))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extraction',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    source = args.extraction.resolve()
    out = args.output.resolve()
    assert not out.exists()
    owner = json.loads((source/'owner.json').read_text())
    left = owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0,'original layout check deadline exhausted'
    signal.alarm(max(1,math.floor(left)))
    receipt = verify(source/'native_completion.json')
    assert receipt['native_extraction_completed'] and receipt['full_flattened_feedback_captured']
    inventory = ROOT/'build/timing400/release_001/flat_decap_warning_gate_inventory_001'
    verify(inventory/'assessment.json')
    gates = json.loads((inventory/'gates.json').read_text())
    feedback = source/'extraction_feedback.txt'
    text = feedback.read_text()
    matches = re.findall(r'box (-?\d+) (-?\d+) (-?\d+) (-?\d+)\nfeedback add "((?:\\.|[^"\\])*)" \w+',text,re.S)
    entries = [(list(map(int,row[:4])),row[4]) for row in matches]
    assert len(entries)==text.count('feedback add ')==len(gates)==2288
    validate_feedback(entries,gates)
    bad_rail = copy.deepcopy(entries)
    box,message = bad_rail[0]
    bad_rail[0] = (box,message.replace('VGND','WRONG').replace('VPWR','WRONG'))
    bad_box = copy.deepcopy(entries)
    bad_box[0][0][0]+=1
    negative = []
    for label,bad in [('wrong_rail',bad_rail),('wrong_gate_box',bad_box)]:
        try:
            validate_feedback(bad,gates)
        except AssertionError:
            negative.append(label)
        else:
            raise AssertionError('negative feedback control accepted: '+label)
    # Index only the expected decap gates. Exact native device seed positions
    # provide an independent physical association, not a warning-count match.
    buckets = defaultdict(list)
    for index,row in enumerate(gates):
        left,bottom,right,top = row['expected_magic_box']
        for x in range(left//400,right//400+1):
            for y in range(bottom//400,top//400+1):
                buckets[x,y].append(index)
    device_rows = []
    seen = set()
    native = source/'IntegerPLL_400MHz_FilledCapView.ext'
    with native.open() as stream:
        for line in stream:
            if not line.startswith(('device mosfet ','device msubckt ')):
                continue
            f = shlex.split(line)
            if 'fet' not in f[2]:continue
            assert len(f)==19,f
            if f[1]=='msubckt':
                assert f[7].startswith('l=') and f[8].startswith('w=')
                f[7],f[8]=f[7][2:],f[8][2:]
            if not (f[9]==f[13]==f[16] and f[9] in ['VPWR','VGND'] and f[10] in ['VPWR','VGND'] and f[9]!=f[10]):
                continue
            x1,y1,x2,y2 = map(int,f[3:7])
            matched = []
            for index in buckets[x1//400,y1//400]:
                left,bottom,right,top = gates[index]['expected_magic_box']
                if 2*left<x1+x2<2*right and 2*bottom<y1+y2<2*top:
                    matched.append(index)
            assert len(matched)==1,(f,matched)
            index = matched[0]
            assert index not in seen
            seen.add(index)
            row = gates[index]
            assert f[9]==row['expected_missing_terminal_rail']
            assert ('__nfet_' if f[9]=='VGND' else '__pfet_') in f[2]
            left,bottom,right,top = row['expected_magic_box']
            assert int(f[7])*int(f[8])==(right-left)*(top-bottom)
            device_rows.append(dict(gate_index=index,model=f[2],gate=f[10],body=f[9],
                source=f[13],drain=f[16],native_seed=[x1,y1,x2,y2],native_length=int(f[7]),native_width=int(f[8])))
    assert len(seen)==len(gates)==2288
    paths = [Path(__file__).resolve(),source/'native_completion.json',feedback,native,
        inventory/'assessment.json',inventory/'gates.json']
    out.mkdir()
    save(out/'devices.json',device_rows)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'devices.json'):sha(out/'devices.json')},
        complete_feedback_entries=2288,exact_decap_gate_box_matches=2288,
        well_derived_rail_matches=2288,native_moscap_gate_position_and_area_matches=2288,
        native_moscap_drain_source_bulk_equal_correct_rail=True,unclassified_feedback_entries=0,
        duplicate_or_missing_feedback_entries=0,negative_controls_rejected=negative,
        full_flat_terminal_warning_classification_passed=True,
        full_electrical_model_qualified=False,nonlinear_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('All2288 flat warnings match exact decap gates, correct rails, and native MOSCAP geometry; two corrupt controls rejected.')


if __name__=='__main__':
    main()
