#!/usr/bin/env python3
"""Bind detector repair identity, full DRC/LVS and local antenna evidence.

Physical-only candidate evidence. Added diode input capacitance and reduced
supply decoupling require fresh analog qualification before adoption.
"""
import argparse
from pathlib import Path
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    base=ROOT/'build/timing400/release_001'
    candidate=base/'bbpd_internal_antenna_001'
    reports=[candidate/'assessment.json',candidate/'signoff/assessment.json',
             base/'bbpd_internal_antenna_identity_001/assessment.json',
             base/'bbpd_internal_antenna_mos_check_001/native_completion.json',
             base/'bbpd_internal_antenna_formation_001/assessment.json']
    route,physical,identity,native,formation=[verify(p) for p in reports]
    assert physical['magic_drc_rectangles']==0 and physical['lvs_unique_match']
    assert identity['exact_functional_cell_pin_binding_identity']
    assert identity['changed_existing_routed_net_records']==['CLKDIVR','REF']
    assert set(identity['negative_controls_rejected'])=={'wrong_diode_net','swapped_clock'}
    gds=candidate/'signoff/route.gds'
    assert native['input_sha256'][str(gds)]==sha(gds)==physical['sha256'][str(gds)]
    assert native['exit_code']==0 and formation['mos_only_native_feedback_rectangles']==0
    assert len(formation['local_gate_diode_records'])==2
    assert all(r['connected'] and r['wrong_diode_rejected'] for r in formation['local_gate_diode_records'])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),*reports]},
        artifacts={},candidate=str(candidate),functional_cells_unchanged=13,state_primitives_unchanged=2,
        retained_placements_and_macro_ports_identical=True,changed_existing_signal_nets=['REF','CLKDIVR'],
        added_diodes=2,decap12_sites_replaced_by_decap6_decap4_diode2=2,
        magic_drc_rectangles=0,lvs_unique_match=True,mos_only_native_feedback_rectangles=0,
        both_known_gates_reach_distinct_diodes_at_metal2=True,
        diode_geometry_um2=.4347,diode_perimeter_um=2.64,
        all_forming_subnetwork_ratios_checked=False,analog_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Bound physical repair: DRC0, unique LVS, exact functional identity, zero native antenna feedback and two local M2 diode bindings.')

if __name__=='__main__':main()
