#!/usr/bin/env python3
"""Check actual tie/diode geometry conservation across corner export schemas.

Preserve the documented diode scaling and normalize pj/perim names only for
comparison. This does not approve model translation or runtime compatibility.
"""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import shlex
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def exported(records):
    result=Counter()
    for line in records:
        f=line.split()
        assert f[0][0] in ['R','D','X']
        indices=[i for i,v in enumerate(f) if v.startswith('sky130_fd_pr__')]
        assert len(indices)==1
        index=indices[0]
        assert index==3
        params={}
        for token in f[index+1:]:
            name,value=token.split('=')
            name='perim' if name=='pj' else name
            assert name not in params
            params[name]=Decimal(value)
        assert set(params) in [{'w','l'},{'area','perim'}]
        result[(tuple(f[1:index+1]),tuple(sorted(params.items())))]+=1
    return result


def native(records):
    result=Counter()
    for line in records:
        f=shlex.split(line)
        if f[2]=='sky130_fd_pr__res_generic_po':
            assert f[1] in ['devres','rsubckt']
            if f[1]=='rsubckt':
                assert f[9]=='None'
                del f[9]
                assert f[7].startswith('l=') and f[8].startswith('w=')
                f[7],f[8]=f[7][2:],f[8][2:]
            assert len(f)==18
            f[1]='normalized_two_terminal_poly_resistor'
        else:
            assert f[2]=='sky130_fd_pr__diode_pw2nd_05v5' and f[1] in ['ndiode','msubckt']
            assert len(f)==16 and f[7].startswith('a=') and f[8].startswith('p=')
            assert f[9] in ['None',f[13]]
            del f[9]
            f[1]='normalized_two_terminal_diode'
        result[tuple(f)]+=1
    return result


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'primitive_corner_exports_001'
    verify(source/'assessment.json')
    data=json.loads((source/'observations.json').read_text())
    counts={}
    for name in ['hs_tie','hd_tie','hs_diode','hd_diode']:
        normalized={c:native(data[c][name]['native_device_records']) for c in ['min','nom','max']}
        exports={c:exported(data[c][name]['exported_device_and_continuation_records']) for c in ['min','nom','max']}
        assert normalized['min']==normalized['nom']==normalized['max'],name
        assert exports['min']==exports['nom']==exports['max'],name
        count=sum(normalized['nom'].values())
        assert count==(2 if name.endswith('tie') else 1)
        counts[name]=count
        bad=exports['min'].copy()
        bad[next(iter(bad))]-=1
        assert bad!=exports['nom']
    out=base/'primitive_corner_export_audit_001'
    out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),source/'assessment.json',source/'observations.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        corner_controls=12,native_device_counts_by_control=counts,
        normalized_native_geometry_and_connectivity_preserved=True,
        exported_device_geometry_and_terminal_order_preserved=True,
        primitive_pj_and_wrapper_perim_normalized_for_comparison_only=True,
        diode_geometry_scaling_preserved_without_modification=True,missing_device_controls_rejected=True,
        actual_hs_geometry_matches_legacy_hd_geometry=False,
        runtime_compatibility_or_model_translation_qualified=False,
        full_layout_rc_enclosure_qualified=False,native_analog_jobs_added=0,
        release_qualified=False,adopted=False,scope=__doc__))
    print('All12 tie/diode corner controls preserve native geometry and exported terminal parameters; runtime/model equivalence remains separate.')


if __name__=='__main__':
    main()
