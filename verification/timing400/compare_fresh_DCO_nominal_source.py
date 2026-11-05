#!/usr/bin/env python3
"""Compare fresh nominal DCO native output with the retained pre-RC source.

Prove same GDS/native C and device data were traced, despite the legacy RC
backannotation invalidation. Equality does not qualify spatial placement or
junction partitioning, or restore eligibility of the retired RC model.
"""
from pathlib import Path
from check_isolated_magic_stock_v3 import matrix,devices
from audit_active_dco_rc_capacitance import parse
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';check=base/'DCO_full_C_trace_controls_002/assessment.json'
    assert verify(check)['full_DCO_trace_accounting_passed']
    old=base/'active_dco_lumped_capacitance_export_001/lumped_full.spice'
    fresh=check.parent/'nom_trace/control.spice'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    old_ext=ROOT/f'build/timing450/dco_c1_fine_load_001/rcx_160/{top}.ext'
    fresh_ext=fresh.parent/(top+'.ext')
    a,b=parse(old),parse(fresh);cm=matrix(old)==matrix(fresh);dv=devices(old_ext)==devices(fresh_ext)
    same=cm and dv and a['X']==b['X'] and a['ports']==b['ports']
    out=base/'fresh_DCO_nominal_source_comparison_001';out.mkdir(exist_ok=False)
    save(out/'comparison.json',dict(exact_positive_C_matrix_equal=cm,exact_native_device_records_equal=dv,
        exact_exported_X_devices_equal=a['X']==b['X'],ports_equal=a['ports']==b['ports'],
        source_C_records=len(a['C']),fresh_C_records=len(b['C']),all_source_data_equal=same))
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),
        Path(__file__).with_name('check_isolated_magic_stock_v3.py'),check,old,fresh,old_ext,fresh_ext]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'comparison.json'):sha(out/'comparison.json')},
        exact_nominal_pre_RC_source_equivalence=same,legacy_RC_model_requalified=False,
        C_and_junction_spatial_distribution_qualified=False,transient_error_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Fresh nominal DCO source equals retained pre-RC extraction:',same,'; retired RC model remains disqualified.')


if __name__=='__main__':main()
