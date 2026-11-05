#!/usr/bin/env python3
"""Retain exact source-context C/device differences; do not equate unproved views."""
from collections import Counter
from pathlib import Path
from decimal import Decimal
from check_isolated_magic_stock_v3 import matrix,devices
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';receipt=base/'fresh_DCO_nominal_source_comparison_001/assessment.json'
    assert not verify(receipt)['exact_nominal_pre_RC_source_equivalence']
    old=base/'active_dco_lumped_capacitance_export_001/lumped_full.spice'
    fresh=base/'DCO_full_C_trace_controls_002/nom_trace/control.spice'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    old_ext=ROOT/f'build/timing450/dco_c1_fine_load_001/rcx_160/{top}.ext';fresh_ext=fresh.parent/(top+'.ext')
    a,b=matrix(old),matrix(fresh);rows=[]
    for k in sorted(a.keys()|b.keys()):
        x,y=a.get(k,Decimal(0)),b.get(k,Decimal(0))
        if x!=y:rows.append(dict(nodes=list(k),before_ff=str(x*Decimal('1e15')),fresh_ff=str(y*Decimal('1e15')),delta_ff=str((y-x)*Decimal('1e15'))))
    da,db=devices(old_ext),devices(fresh_ext)
    out=base/'fresh_DCO_nominal_source_difference_001';out.mkdir(exist_ok=False)
    save(out/'C_differences.json',rows);save(out/'native_device_record_differences.json',dict(old_only=list((da-db).elements()),fresh_only=list((db-da).elements())))
    paths=[Path(__file__).resolve(),receipt,old,fresh,old_ext,fresh_ext,Path(__file__).with_name('check_isolated_magic_stock_v3.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        changed_C_pairs=len(rows),maximum_C_difference_ff=str(max(abs(Decimal(r['delta_ff'])) for r in rows)),
        changed_native_device_records_old=sum((da-db).values()),changed_native_device_records_fresh=sum((db-da).values()),
        equivalence_qualified=False,release_qualified=False,adopted=False))
    print('Fresh nominal source differences:',len(rows),'C pairs; first examples',rows[:3])
    print('Native device record differences:',list((da-db).elements())[:1],list((db-da).elements())[:1])


if __name__=='__main__':main()
