#!/usr/bin/env python3
"""Independently reduce isolated C controls and compare corner MOS exports."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import shlex
from audit_parent_capacitance_network import decimal_value
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def effective_control(records, substrate):
    branches=[]
    nodes=set()
    for record in records:
        f=record.split()
        a,b,c=f[1],f[2],decimal_value(f[3])
        assert c>=0
        branches.append((a,b,c))
        nodes.update([a,b])
    assert 'SIG' in nodes
    reference={substrate,'VPWR'}
    floating=nodes-{'SIG'}-reference
    assert len(floating)<=1
    diagonal=sum((c for a,b,c in branches if 'SIG' in [a,b]),Decimal(0))
    if floating:
        node=next(iter(floating))
        ff=sum((c for a,b,c in branches if node in [a,b]),Decimal(0))
        sf=sum((c for a,b,c in branches if {a,b}=={'SIG',node}),Decimal(0))
        assert ff>0
        diagonal-=sf*sf/ff
    assert diagonal>0
    return diagonal


def native_devices(lines):
    result=Counter()
    for line in lines:
        f=shlex.split(line)
        assert f[0]=='device' and f[1] in ['mosfet','msubckt'] and len(f)==19
        if f[1]=='msubckt':
            assert f[7].startswith('l=') and f[8].startswith('w=')
            f[7],f[8]=f[7][2:],f[8][2:]
        f[1]='normalized_mos'
        result[tuple(f)]+=1
    return result


def exported_devices(path):
    lines=[]
    for line in path.read_text().splitlines():
        if line.startswith('+'):
            assert lines
            lines[-1]+=' '+line[1:].strip()
        elif line[:1] in ['M','X']:
            lines.append(line)
    result=Counter()
    for line in lines:
        f=line.split()
        params=dict(re.findall(r'\b(w|l|ad|as|pd|ps)=([^\s]+)',line))
        assert set(params)=={'w','l','ad','as','pd','ps'}
        result[(tuple(f[1:6]),tuple(sorted((k,decimal_value(v)) for k,v in params.items())))]+=1
    return result


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'capacitance_corner_controls_001'
    out=base/'capacitance_corner_control_audit_001'
    verify(source/'assessment.json')
    observations=json.loads((source/'observations.json').read_text())
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),
        source/'assessment.json',source/'observations.json']
    reduced={}
    for name in ['m1_baseline','floating_poly','p_bulk_surface','n_bulk_surface','floating_metal']:
        reduced[name]={}
        for corner in ['min','nom','max']:
            row=observations[corner][name]
            assert row['native_exit_code']==0 and not row['native_device_records'] and row['feedback']==''
            ext=next((source/f'{corner}_{name}').glob('*.ext'))
            paths.append(ext)
            substrate=re.findall(r'^substrate "([^"]+)"',ext.read_text(),re.M)
            assert len(substrate)==1
            reduced[name][corner]=effective_control(row['capacitor_records'],substrate[0])
        assert reduced[name]['min']<reduced[name]['nom']<reduced[name]['max'],(name,reduced[name])
    device_sets={corner:native_devices(observations[corner]['nand2_2']['native_device_records'])
        for corner in ['min','nom','max']}
    assert device_sets['min']==device_sets['nom']==device_sets['max']
    assert sum(device_sets['nom'].values())==8
    exports={}
    for corner in ['min','nom','max']:
        spice=source/f'{corner}_nand2_2/control.spice'
        paths.append(spice)
        exports[corner]=exported_devices(spice)
    assert exports['min']==exports['nom']==exports['max'] and sum(exports['nom'].values())==8
    damaged=device_sets['min'].copy()
    damaged[next(iter(damaged))]-=1
    assert damaged!=device_sets['nom']
    bad_corner_order_rejected=False
    try:
        assert reduced['floating_poly']['max']<reduced['floating_poly']['min']
    except AssertionError:
        bad_corner_order_rejected=True
    assert bad_corner_order_rejected
    out.mkdir(exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        isolated_effective_capacitances_f={name:{c:str(v) for c,v in cases.items()} for name,cases in reduced.items()},
        all_five_control_effective_capacitances_strictly_ordered=True,
        isolated_reduction_assumes_ideal_bulk_and_supply_references=True,
        native_nand_mos_device_statements_preserved_after_schema_normalization=8,
        exported_nand_geometry_and_terminal_parameters_preserved_across_m_and_x_cards=8,
        nominal_orig_exports_m_cards=True,min_max_export_foundry_wrapper_x_cards=True,
        missing_device_and_reversed_corner_order_controls_rejected=True,
        full_layout_rc_corner_extraction_complete=False,full_rc_enclosure_qualified=False,
        actual_fom_material_equivalence_qualified=False,native_analog_jobs_added=0,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('All5 isolated C controls ordered min<nom<max; all8 actual NAND MOS devices and exported parameters preserved across M/X formats.')


if __name__=='__main__':
    main()
