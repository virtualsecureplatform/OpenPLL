#!/usr/bin/env python3
"""Recompute PDK corner R on the complete fixed native geometry/voltage mesh.

Every wire nominal value must reproduce the native float32 sheet*length/width
formula exactly. Contact array multiplicity is recovered from nominal native R
and checked against the native formula; independent cut geometry is a separate
qualification. No ideal-conductor merging or topology changes occur.
"""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import struct
import time

from compile_local_C_operators_v2 import digest, save


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


WIRE = {'pdiff': '(*pdiff,*psd)/active', 'ndiff': '(*ndiff,nsd)/active',
    'nsubdiff': '(*ndiff,nsd)/active', 'pwell': '(pwell,isosub)/well', 'nwell': '(nwell)/well',
    'poly': '(allpolynonres)/active', 'scnmos': '(allpolynonres)/active',
    'scpmoshvt': '(allpolynonres)/active', 'locali': '(allli)/locali',
    **{f'metal{i}': f'(allm{i})/metal{i}' for i in range(1, 6)}}
CONTACT = {'pdiffc': 'pdc,psc', 'ndiffc': 'ndc,nsc', 'psubdiffcont': 'pdc,psc',
    'nsubdiffcont': 'ndc,nsc', 'polycont': 'pc,xpc', 'viali': 'mcon',
    'via1': 'm2c', 'via2': 'm3c', 'via3': 'via3', 'via4': 'via4'}


def tables(path):
    result = {c: {} for c in ['nom', 'min', 'max']}
    variant = None
    in_extract = False
    for number, text in enumerate(path.open(), 1):
        f = text.split('#', 1)[0].split()
        if not f:
            continue
        if f[0] == 'extract':
            in_extract = True
        elif in_extract and f[0] == 'end':
            in_extract = False
        if not in_extract:
            continue
        if f[0] == 'variants':
            variant = {'(),(orig),(si)': 'nom', '(hrhc),(hrlc)': 'max', '(lrhc),(lrlc)': 'min'}.get(''.join(f[1:]))
        elif variant and f[0] in ['resist', 'contact']:
            key = f[0], f[1]
            assert key not in result[variant]
            result[variant][key] = dict(value_milliohm=int(f[2]), source_line=number, text=text.rstrip())
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    family = base/'DCO_complete_domain_model_primitives_001'
    geometry = {r['index']: r for r in map(json.loads, (family/'wire_geometry.jsonl').open())}
    assert len(geometry) == 130708
    tech = root/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    table = tables(tech)
    out = base/'DCO_domain_R_corners_002'
    out.mkdir(exist_ok=False)
    save(out/'PDK_rules.json', {c: [dict(rule=list(k), **v) for k, v in rules.items()]
        for c, rules in table.items()})
    counts = Counter()
    contact_arrays = Counter()
    files = {c: (out/(c+'_wire_R_unqualified.spice')).open('x') for c in ['min', 'nom', 'max']}
    for c, stream in files.items():
        stream.write('* Complete fixed native mesh; PDK '+c+' R values. Runtime unqualified.\n')
    records = (out/'branches.jsonl').open('x')
    try:
        for text in (family/'branches.jsonl').open():
            r = json.loads(text)
            index, material = r['index'], r['material']
            native = float(r['native_milliohm'])
            if index in geometry:
                g = geometry[index]
                assert g['private_nodes'] == r['private_nodes']
                axis = 0 if r['status'] & 0x600 == 0x200 else 1
                assert r['status'] & 0x600 in [0x200, 0x400]
                a, b = g['creation_breakpoints_internal']
                length, width = b[axis]-a[axis], g['width']
                assert length > 0 and width > 0
                key = 'resist', WIRE[material]
                def value(corner):
                    sheet = table[corner][key]['value_milliohm']
                    return f32(f32(f32(sheet)*f32(length))/f32(width))
                details = dict(kind='sheet', length_internal=length, width_internal=width)
            else:
                assert not r['status'] & 0x600
                key = 'contact', CONTACT[material]
                nominal_via = table['nom'][key]['value_milliohm']
                multiplicity = round(nominal_via/native)
                assert multiplicity > 0
                def value(corner):
                    return f32(f32(table[corner][key]['value_milliohm'])/f32(multiplicity))
                details = dict(kind='contact', native_parallel_cut_count=multiplicity,
                    cut_count_independently_geometry_checked=False)
                contact_arrays[material, multiplicity] += 1
            values = {c: value(c) for c in files}
            assert values['nom'] == native, (index, material, native, values, details)
            assert 0 < values['min'] <= values['nom'] <= values['max']
            for c, stream in files.items():
                ohm = Decimal(str(values[c]))/1000
                stream.write(f"RDOM_{index} {' '.join(r['private_nodes'])} {ohm}\n")
            records.write(json.dumps(dict(index=index, private_nodes=r['private_nodes'],
                original_conductor=r['original_conductor'], material=material, PDK_rule=list(key),
                resistance_milliohm=values, **details))+'\n')
            counts[material] += 1
            if index % 10000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        assert sum(counts.values()) == 166286
    finally:
        records.close()
        for stream in files.values():
            stream.close()
    # Independent readback proves topology and each serialized corner value.
    reference = [json.loads(s) for s in (out/'branches.jsonl').open()]
    for c in files:
        lines = [s.split() for s in (out/(c+'_wire_R_unqualified.spice')).open() if not s.startswith('*')]
        assert len(lines) == len(reference)
        for f, r in zip(lines, reference):
            assert f[0] == 'RDOM_'+str(r['index']) and f[1:3] == r['private_nodes']
            assert Decimal(f[3])*1000 == Decimal(str(r['resistance_milliohm'][c]))
    inputs = [Path(__file__).resolve(), owner, tech, family/'assessment.json', family/'branches.jsonl',
        family/'wire_geometry.jsonl', root/'build/timing400/magic_R_tile_domain_source_001/resis/ResMakeRes.c']
    artifacts = [p for p in out.iterdir() if p.is_file()]
    result = dict(all166286_nominal_values_reproduce_native_float32_formulas_exactly=True,
        ordinary_wire_branches=130708, finite_contact_branches=35578,
        fixed_geometry_topology_and_private_node_IDs_preserved=True,
        PDK_min_nom_max_values_positive_and_ordered=True, all_three_decks_exact_readback_passed=True,
        counts_by_material=dict(counts), contact_array_counts=[dict(material=m, cuts=n, branches=count)
            for (m, n), count in sorted(contact_arrays.items())],
        independent_contact_cut_geometry_qualified=False, discretization_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in artifacts})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts', 'contact_array_counts']}, indent=2))


if __name__ == '__main__':
    main()
