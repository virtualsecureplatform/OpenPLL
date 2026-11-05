#!/usr/bin/env python3
"""Audit full-layout corner capacitors including foundry-wrapper device nodes.

Keep floating branches explicit; sums are matrix diagonal observations, not
Miller/effective loads, passive-model proofs or a timing enclosure. Compare
critical-node sums independently with Decimal arithmetic and retain negatives.
"""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal,localcontext
import json
import math
from pathlib import Path
import re
import signal
from datetime import datetime,timezone
import time
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

SCALE={'':1.,'f':1e-15,'p':1e-12,'n':1e-9,'u':1e-6,'m':1e-3,'k':1e3,'meg':1e6,'g':1e9}
NUMBER=re.compile(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(meg|[fpnumkg]?)$',re.I)

def value(raw):
    match=NUMBER.fullmatch(raw);assert match,raw
    result=float(match[1])*SCALE[match[2].lower()];assert math.isfinite(result),raw
    return result

def decimal_value(raw):
    match=NUMBER.fullmatch(raw);assert match,raw
    return Decimal(match[1])*Decimal(str(SCALE[match[2].lower()]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['extraction','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();source=args.extraction.resolve();out=args.output.resolve();base=ROOT/'build/timing400/release_001'
    owner=json.loads((source/'owner.json').read_text());deadline=owner['deadline_uptime'];left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    receipt=verify(source/'native_completion.json');assert receipt['exit_code']==0 and receipt['native_extraction_completed']
    spice=source/'capacitance.spice';route=base/'parent_dco_antenna_targeted_011/route.def';_,_,nets=design(route);parents=set(nets);assert len(parents)==359
    critical={'PLLOUT','REFCLK','BBPD_RESET_N'}&parents
    counts=Counter();active_nodes=set();negative=[];minimum=None;maximum=None;branch_data=defaultdict(list);seen=set()
    paths=[Path(__file__).resolve(),source/'native_completion.json',source/'owner.json',source/'extract.log',spice,route]
    pins={str(p):sha(p) for p in paths};out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(deadline_uptime=deadline,original_owner=str(source/'owner.json'),total_budget_restarted=False))
    with spice.open() as stream:
        for line in stream:
            if not line or line[0] in '*+.\n':continue
            fields=line.split();kind=fields[0][0].upper();counts[kind]+=1
            if kind in {'M','R','D','X'}:
                if kind=='X':
                    model_indices=[i for i,f in enumerate(fields) if f.startswith('sky130_fd_pr__')]
                    assert len(model_indices)==1,line
                    model_index=model_indices[0];n=model_index-1;model=fields[model_index]
                    if n==4:
                        assert 'fet' in model,line
                        counts['X_MOS']+=1
                    elif n==2 and '__diode_' in model:counts['X_DIODE']+=1
                    elif n==2 and '__res_' in model:counts['X_RESISTOR']+=1
                    else:raise AssertionError('unhandled foundry wrapper: '+line)
                else:n=4 if kind=='M' else 2
                assert len(fields)>n
                active_nodes.update(fields[1:1+n]);seen.update(parents.intersection(fields[1:1+n]));continue
            if kind!='C':continue
            assert len(fields)>=4,line
            a,b,raw=fields[1:4];c=value(raw)
            minimum=c if minimum is None else min(c,minimum);maximum=c if maximum is None else max(c,maximum)
            if c<0:
                counts['negative_capacitors']+=1
                if len(negative)<30:negative.append(line.rstrip())
            if c==0:counts['zero_capacitors']+=1
            if a in parents:branch_data[a].append((b,c,raw));seen.add(a)
            if b in parents:branch_data[b].append((a,c,raw));seen.add(b)
            if counts['C']%5000000==0:
                print('Audited',counts['C'],'capacitors.',flush=True)
                assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    assert counts['C']==receipt['capacitor_records']
    rails={'0','VGND','VPWR','VSUBS'}
    records=[];independent=[]
    for parent in sorted(parents):
        branches=branch_data[parent]
        sums={
            'signed_diagonal_f':math.fsum(c for other,c,raw in branches),
            'positive_diagonal_f':math.fsum(c for other,c,raw in branches if c>0),
            'negative_diagonal_f':math.fsum(c for other,c,raw in branches if c<0),
            'to_explicit_rail_nodes_f':math.fsum(c for other,c,raw in branches if other in rails),
            'to_other_parent_nodes_f':math.fsum(c for other,c,raw in branches if other in parents and other not in rails),
            'to_active_device_nodes_f':math.fsum(c for other,c,raw in branches if other in active_nodes and other not in parents and other not in rails),
            'to_capacitor_only_nodes_f':math.fsum(c for other,c,raw in branches if other not in active_nodes and other not in parents and other not in rails)}
        records.append(dict(parent_node=parent,capacitor_branches=len(branches),seen_in_components=parent in seen,**sums))
        if parent in critical:
            with localcontext() as ctx:
                ctx.prec=50;exact=sum((decimal_value(raw) for other,c,raw in branches),Decimal(0))
            assert abs(Decimal(str(sums['signed_diagonal_f']))-exact)<=max(abs(exact)*Decimal('1e-12'),Decimal('1e-28'))
            independent.append(dict(parent_node=parent,decimal_signed_diagonal_f=str(exact),float_signed_diagonal_f=sums['signed_diagonal_f']))
    save(out/'parent_nodes.json',records);save(out/'independent_sums.json',independent)
    for p,d in pins.items():assert sha(p)==d,p
    log=(source/'extract.log').read_text()
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        component_record_counts=dict(counts),active_device_nodes=len(active_nodes),capacitor_minimum_f=minimum,capacitor_maximum_f=maximum,
        missing_parent_nodes=sorted(parents-seen),negative_capacitor_examples=negative,
        parent_nodes=359,parent_nodes_with_capacitance=sum(bool(branch_data[p]) for p in parents),independent_decimal_sums=len(independent),
        native_extraction_warning_count=int(re.search(r'Total of (\d+) warnings\.',log)[1]),floating_capacitive_branches_preserved=True,
        reported_sums_are_effective_loads=False,passivity_qualified=False,full_capacitance_coverage_qualified=False,
        resistance_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Raw network audited:',dict(counts),'missing parents',sorted(parents-seen),flush=True)
    for row in records:
        if row['parent_node'] in critical:print(row,flush=True)

if __name__=='__main__':main()
