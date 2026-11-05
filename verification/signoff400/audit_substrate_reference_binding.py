"""Identify the native ideal substrate and verify selected relocated caps."""
import argparse
from fractions import Fraction as F
import json
import mmap
from pathlib import Path
import struct
import time
from common import ROOT, save, sha
from resources import lease


def x87(data):
    significand, word = struct.unpack('<QH', data)
    exponent = word & 32767
    if exponent == 32767:
        raise ValueError('finite extended-precision matrix value required')
    power = (exponent if exponent else 1)-16383-63
    value = F(significand << power) if power >= 0 else F(significand, 1 << -power)
    return -value if word & 32768 else value


def entry(data, count, a, b):
    if a > b:
        a, b = b, a
    key = (a << 32)|b
    lo, hi = 0, count
    while lo < hi:
        mid = (lo+hi)//2
        if struct.unpack_from('<Q', data, 16+40*mid)[0] < key:
            lo = mid+1
        else:
            hi = mid
    if lo == count or struct.unpack_from('<Q', data, 16+40*lo)[0] != key:
        return F(0)
    return x87(data[24+40*lo:34+40*lo])


def run(reference, delta, mapping, native, output):
    reference, delta, mapping, native, out = (p.resolve() for p in (reference, delta, mapping, native, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    receipts = [p/'assessment.json' for p in (reference, delta, mapping, native)]
    r, d, m, n = [json.loads(p.read_text()) for p in receipts]
    if d['input_sha256'].get(str(receipts[0])) != sha(receipts[0]) or r['input_sha256'].get(str(receipts[2])) != sha(receipts[2]):
        raise ValueError('reference/delta/conductor map lineage mismatch')
    compilers = [Path(p) for p in m['input_sha256'] if p.endswith('/compiled_charge/assessment.json')]
    if len(compilers) != 1 or sha(compilers[0]) != m['input_sha256'][str(compilers[0])]:
        raise ValueError('conductor-map compiler identity')
    compiled = json.loads(compilers[0].read_text())
    if compiled['input_sha256'].get(str(receipts[3])) != sha(receipts[3]):
        raise ValueError('native trace/compiler identity mismatch')
    names = mapping/'native/net_names.jsonl'
    ext = native/'trace/Prototype400_FilledCapacitanceView.ext'
    matrix = Path(r['native_output_reference_matrix'])
    report = delta/'native_reference_delta.report.json'
    source = ROOT/'build/timing400/magic_C_owner_source_001/extract/ExtCouple.c'
    paths = [*receipts, compilers[0], names, ext, matrix, report, source, Path(__file__).resolve()]
    with lease(2, 8, deadline):
        pins = {str(p): sha(p) for p in paths}
        if pins[str(names)] != m['artifacts'][str(names)] or pins[str(ext)] != n['artifacts'][str(ext)]:
            raise ValueError('native EXT or conductor names changed')
        if pins[str(matrix)] != r['artifacts'][str(matrix)] or pins[str(report)] != d['artifacts'][str(report)]:
            raise ValueError('native reference or delta report changed')
        candidates = [row[1] for row in json.loads(report.read_text())['largest_differences']
                      if row[0] == 0 and row[1] > 0 and row[3] > 0][:2]
        if len(candidates) != 2:
            raise ValueError('two explicit-reference relocation controls required')
        targets = {}
        with names.open() as stream:
            for raw in stream:
                number, name = json.loads(raw)
                if number in candidates:
                    targets[number] = name
        wanted = set(targets.values())
        caps, substrate = {}, None
        with ext.open() as stream:
            for line in stream:
                if line.startswith('substrate "'):
                    substrate = line.split('"', 2)[1]
                elif line.startswith('node "'):
                    fields = line.split('"', 2)
                    if fields[1] in wanted:
                        caps[fields[1]] = F(fields[2].split()[1])
                if substrate is not None and len(caps) == len(wanted):
                    break
        if substrate is None or len(caps) != 2:
            raise ValueError('native substrate declaration and selected node caps required')
        substrate_id = None
        with names.open() as stream:
            for raw in stream:
                number, name = json.loads(raw)
                if name == substrate:
                    substrate_id = number
                    break
        if not substrate_id:
            raise ValueError('native substrate conductor must be distinct from the abstract reference')
        code = source.read_text()
        if 'extRelocateSubstrateCoupling' not in code or 'rbp->nreg_cap += cap;' not in code or 'rtp->nreg_cap += cap;' not in code:
            raise ValueError('native substrate relocation source behavior differs')
        results = []
        with matrix.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            if data[:8] != b'SPCRUN01':
                raise ValueError('native trace reference format')
            count = struct.unpack_from('<Q', data, 8)[0]
            if len(data) != 16+40*count:
                raise ValueError('native trace reference size')
            for number, name in targets.items():
                abstract, actual_substrate = entry(data, count, 0, number), entry(data, count, substrate_id, number)
                predicted = -(abstract+actual_substrate)
                tolerance = F(1, 100000000)+abs(caps[name])*F(1, 100000)
                if abs(predicted-caps[name]) > tolerance:
                    raise ValueError('folded substrate trace cap differs from native printed cap')
                results.append(dict(conductor_id=number, original_conductor=name,
                     abstract_reference_offdiagonal=float(abstract), substrate_offdiagonal=float(actual_substrate),
                     folded_ground_capacitance=float(predicted), printed_native_ground_capacitance=float(caps[name]),
                     absolute_tolerance=float(tolerance)))
        if any(sha(Path(p)) != value for p, value in pins.items()):
            raise ValueError('substrate binding audit input changed')
        save(out/'cases.json', results)
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(out/'cases.json'): sha(out/'cases.json')},
             declared_native_substrate=substrate, native_substrate_conductor_id=substrate_id,
             abstract_reference_conductor_id=0, selected_relocation_controls_pass=len(results),
             native_ideal_comparison_requires_reference_substrate_identification=True,
             reference_matrix_semantics='unfolded_native_trace_delta_matrix',
             full_printed_native_matrix_reconstruction_verified=False,
             finite_R_substrate_target_assignment_qualified=False, scalar_rounding_spatial_assignment_complete=False,
             physical_RC_qualified=False, release_qualified=False))
        print(json.dumps(dict(substrate=substrate, conductor_id=substrate_id, selected_controls=len(results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'delta', 'mapping', 'native', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.delta, args.mapping, args.native, args.output)
