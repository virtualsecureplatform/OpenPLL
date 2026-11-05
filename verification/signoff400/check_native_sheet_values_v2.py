#!/usr/bin/env python3
"""Compare documented nominal sheets to native binary32 branch arithmetic.

All chain rows are retained in coverage counts. This checks nominal extraction
consistency, not physical sheet/PVT accuracy, device interfaces or C attachment.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import time
from common import ROOT, save, sha
from nominal_sheet_resistance_v3 import parse


def f32(value):
    return struct.unpack('=f', struct.pack('=f', value))[0]


def expected(sheet, length, width):
    if sheet <= 0 or length <= 0 or width <= 0:
        raise ValueError('positive sheet and segment geometry required')
    return f32(f32(f32(float(sheet))*f32(float(length)))/f32(float(width)))


def check_row(row, sheets):
    material, axis, box = row['raw_material'], row['flow_axis'], row['tile_box_internal']
    result, failures = Counter(), []
    for index, segment in enumerate(row['segments']):
        result['native_segments'] += 1
        if material not in sheets:
            result['segments_without_documented_sheet'] += 1
            continue
        if axis not in (0, 1) or segment[1] <= segment[0] or box[3-axis] <= box[1-axis]:
            result['segments_with_unsupported_geometry'] += 1
            continue
        value = expected(sheets[material], segment[1]-segment[0], box[3-axis]-box[1-axis])
        observed = float(segment[4])
        result['segments_compared'] += 1
        if observed == value:
            result['binary32_exact_matches'] += 1
        else:
            result['binary32_mismatches'] += 1
            failures.append(dict(segment_index=index, observed=observed, expected=value))
    return result, failures


def run(chains, output):
    chains, out = Path(chains).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    save(out/'status.json', dict(state='checking_native_nominal_sheet_arithmetic', release_qualified=False))
    try:
        receipt = chains/'assessment.json'
        r = json.loads(receipt.read_text())
        source = chains/'native/chains.jsonl'
        tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
        native = ROOT/'build/timing400/magic_R_tile_domain_source_001/resis/ResMakeRes.c'
        code = native.read_text()
        for name in ('exts_sheetResist[resistor->rr_tt]', '(float)height', '(float)width',
                     '(float)(p2->br_loc.p_x - p1->br_loc.p_x)',
                     '(float)(p2->br_loc.p_y - p1->br_loc.p_y)'):
            if name not in code:
                raise ValueError('native arithmetic source changed')
        pins = {str(p): sha(p) for p in (receipt, tech, native, Path(__file__).resolve(),
                Path(__file__).with_name('common.py'), Path(__file__).with_name('nominal_sheet_resistance.py'),
                Path(__file__).with_name('nominal_sheet_resistance_v2.py'), Path(__file__).with_name('nominal_sheet_resistance_v3.py'))}
        sheets = parse(tech.read_text())
        totals, materials = Counter(), {}
        digest = hashlib.sha256()
        rows = 0
        with source.open('rb') as stream, (out/'mismatches.jsonl').open('x') as failures:
            for rows, line in enumerate(stream, 1):
                if rows % 1000 == 0 and time.monotonic()-start >= 43200:
                    raise TimeoutError('nominal sheet check deadline')
                digest.update(line)
                row = json.loads(line)
                counts, bad = check_row(row, sheets)
                totals.update(counts)
                materials.setdefault(row['raw_material'], Counter()).update(counts)
                for failure in bad:
                    failures.write(json.dumps(dict(source_chain_row=rows,
                        native_group_id=row['native_group_id'], raw_material=row['raw_material'], **failure))+'\n')
        if digest.hexdigest() != r['artifacts'][str(source)] or rows != r['tile_axis_chains']:
            raise ValueError('complete chain source mismatch')
        if totals['native_segments'] != r['wire_segments']:
            raise ValueError('native segment coverage mismatch')
        for p, h in pins.items():
            if sha(p) != h:
                raise ValueError('input changed: '+p)
        pins[str(source)] = digest.hexdigest()
        result = dict(input_sha256=pins, source_chains=rows, counts=dict(totals),
                      material_counts={k: dict(v) for k, v in materials.items()},
                      artifacts={str(out/'mismatches.jsonl'): sha(out/'mismatches.jsonl')},
                      nominal_native_arithmetic_consistent=totals['binary32_mismatches'] == 0,
                      exact_native_build_lineage_revalidated=False,
                      resistance_PVT_qualified=False, physical_RC_qualified=False,
                      runtime_model_eligible=False, release_qualified=False, elapsed_s=time.monotonic()-start)
        save(out/'assessment.json', result)
        save(out/'status.json', dict(state='nominal_native_arithmetic_checked' if
             result['nominal_native_arithmetic_consistent'] else 'nominal_native_arithmetic_nonpass',
             release_qualified=False, elapsed_s=result['elapsed_s']))
        return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chains', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.chains, a.output)))
