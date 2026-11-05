#!/usr/bin/env python3
"""Remove exactly-zero corner capacitors while preserving all foundry wrappers.

No positive capacitor, device card, value or floating branch is approximated.
This reduces representation size, not electrical qualification requirements.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import time
from audit_parent_capacitance_network import NUMBER
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['extraction','network-audit','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();source=args.extraction.resolve();audit=args.network_audit.resolve();out=args.output.resolve()
    owner=json.loads((source/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    receipt=verify(audit/'assessment.json');spice=source/'capacitance.spice';assert sha(spice)==receipt['input_sha256'][str(spice)]
    original_counts=receipt['component_record_counts'];assert original_counts.get('negative_capacitors',0)==0
    files=[Path(__file__).resolve(),Path(__file__).with_name('audit_corner_capacitance_network.py'),source/'owner.json',audit/'assessment.json',spice]
    pins={str(p):sha(p) for p in files};out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(deadline_uptime=owner['deadline_uptime'],original_owner=str(source/'owner.json'),total_budget_restarted=False))
    target=out/'capacitance_positive.spice';kept=removed=0;devices=Counter();device_digest=hashlib.sha256()
    with spice.open('rb') as incoming,target.open('xb') as outgoing:
        outgoing.write(b'* Diagnostic: only exactly-zero capacitors removed; electrical coverage remains unqualified.\n')
        for rawline in incoming:
            if rawline[:1].upper()==b'C':
                parts=rawline.split();value=parts[3].decode();match=NUMBER.fullmatch(value);assert match,value
                coefficient=Decimal(match[1]);assert coefficient>=0,value
                if coefficient==0:removed+=1;continue
                kept+=1
            elif rawline[:1].upper() in [b'M',b'D',b'R',b'X']:
                devices[rawline[:1].decode().upper()]+=1;device_digest.update(rawline)
            elif rawline[:1]==b'+':device_digest.update(rawline)
            outgoing.write(rawline)
    assert removed==original_counts['zero_capacitors'] and kept+removed==original_counts['C']
    assert all(devices[kind]==original_counts.get(kind,0) for kind in ['M','D','R','X'])
    independent_digest=hashlib.sha256();new_caps=0
    with target.open('rb') as check:
        for line in check:
            if line[:1].upper() in [b'M',b'D',b'R',b'X'] or line[:1]==b'+':independent_digest.update(line)
            if line[:1].upper()==b'C':new_caps+=1
    assert new_caps==kept and device_digest.hexdigest()==independent_digest.hexdigest()
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        original_capacitor_records=kept+removed,removed_exact_zero_capacitors=removed,retained_positive_capacitors=kept,
        unchanged_device_records=dict(devices),unchanged_device_and_continuation_sha256=device_digest.hexdigest(),
        no_nonzero_capacitor_values_changed=True,floating_branches_preserved=True,zero_only_unreferenced_nodes_need_no_spice_declarations=True,
        representation_reduction_exact_for_parsed_network=True,full_capacitance_coverage_qualified=False,
        physical_timing_qualified=False,model_adopted=False,release_qualified=False,scope=__doc__))
    print('Removed',removed,'exact-zero C cards; retained',kept,'positive C cards and all active/resistor devices unchanged.',flush=True)

if __name__=='__main__':main()
