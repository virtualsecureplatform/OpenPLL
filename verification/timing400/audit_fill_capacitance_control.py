#!/usr/bin/env python3
"""Independently recompute the missing floating-fill control capacitance."""
from decimal import Decimal,localcontext
from pathlib import Path
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';control=base/'fill_capacitance_control_001'
    c=verify(control/'assessment.json');rows=c['controls'];scales={'f':Decimal('1e-15'),'p':Decimal('1e-12'),'n':Decimal('1e-9')}
    def parse(records):
        caps={}
        for line in records:
            name,a,b,value,*tail=line.split();key=tuple(sorted((a,b)));assert key not in caps
            caps[key]=Decimal(value[:-1])*scales[value[-1].lower()]
        return caps
    base_caps=parse(rows['no_tile']['capacitor_records']);stock=parse(rows['fill_purpose']['capacitor_records']);drawn=parse(rows['drawing_purpose']['capacitor_records'])
    assert base_caps==stock and len(stock)==1
    key=tuple(sorted(('SIG','VSUBS')));ground=stock[key];assert ground>0 and drawn[key]==ground
    others={n for pair in drawn for n in pair}-{'SIG','VSUBS'};assert len(others)==1
    floating=others.pop();signal_to_fill=drawn[tuple(sorted(('SIG',floating)))];fill_to_sub=drawn[tuple(sorted((floating,'VSUBS')))]
    assert signal_to_fill>0 and fill_to_sub>0 and len(drawn)==3
    with localcontext() as ctx:
        ctx.prec=50
        effective=signal_to_fill*fill_to_sub/(signal_to_fill+fill_to_sub)
        increase=effective/ground*100
    out=base/'fill_capacitance_control_audit_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),control/'assessment.json',*[Path(r['spice']) for r in rows.values()]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        stock_fill_purpose_ignored_in_this_control=True,electrically_represented_tile_has_floating_coupling=True,
        base_signal_to_substrate_f=str(ground),signal_to_floating_tile_f=str(signal_to_fill),tile_to_substrate_f=str(fill_to_sub),
        floating_tile_effective_added_capacitance_f=str(effective),effective_signal_capacitance_increase_percent=str(increase),
        floating_node_not_grounded=True,series_reduction_exact_for_this_two_branch_control=True,
        full_design_fill_capacitance_qualified=False,release_qualified=False,scope=__doc__))
    print('Stock fill purpose adds no modeled C; represented floating tile adds',effective,'F (',increase,'%).')

if __name__=='__main__':main()
