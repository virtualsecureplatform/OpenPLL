"""Bind native trace units to nonzero printed EXT coupling coefficients."""
import argparse
from fractions import Fraction as F
import json
import mmap
from pathlib import Path
import re
import struct
import time
from audit_substrate_reference_binding import entry
from common import ROOT, save, sha
from resources import lease


def run(reference, binding, output):
    reference, binding, out = (p.resolve() for p in (reference, binding, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    receipts = [p/'assessment.json' for p in (reference, binding)]
    ref, bind = [json.loads(p.read_text()) for p in receipts]
    inputs = bind['input_sha256']
    ext, names = [next(Path(p) for p in inputs if p.endswith(suffix))
                  for suffix in ('Prototype400_FilledCapacitanceView.ext', 'net_names.jsonl')]
    matrix = Path(ref['native_output_reference_matrix'])
    code = ROOT/'build/timing400/magic_C_owner_source_001/extract/ExtCouple.c'
    paths = [*receipts, ext, names, matrix, code, Path(__file__).resolve(),
             ROOT/'verification/signoff400/audit_substrate_reference_binding.py']
    with lease(2, 4, deadline):
        pins = {str(p): sha(p) for p in paths}
        if pins[str(ext)] != inputs[str(ext)] or pins[str(names)] != inputs[str(names)]:
            raise ValueError('native printed source identity changed')
        if pins[str(matrix)] != ref['artifacts'][str(matrix)]:
            raise ValueError('native trace reference matrix changed')
        source = code.read_text()
        if 'extGetCapValue(he) / ExtCurStyle->exts_capScale' not in source or '%lg' not in source:
            raise ValueError('native printed scaling or serialization differs')
        scale, samples = None, []
        with ext.open() as stream:
            for line in stream:
                if line.startswith('scale '):
                    scale = F(line.split()[3])
                if line.startswith('cap '):
                    match = re.fullmatch(r'cap "([^"]+)" "([^"]+)" (\S+)\n', line)
                    if not match:
                        raise ValueError('unsupported printed capacitance record')
                    a, b, value = match.groups()
                    if a != b and a != bind['declared_native_substrate'] and b != bind['declared_native_substrate'] and F(value) != 0:
                        samples.append((a, b, value))
                if len(samples) == 3:
                    break
        if scale is None or scale <= 0 or len(samples) != 3:
            raise ValueError('three nonzero native scale controls required')
        wanted = {name for a, b, _ in samples for name in (a, b)}
        identities = {}
        with names.open() as stream:
            for line in stream:
                number, name = json.loads(line)
                if name in wanted:
                    identities[name] = number
        if set(identities) != wanted:
            raise ValueError('printed coupling identity missing')
        cases = []
        with matrix.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            count = struct.unpack_from('<Q', data, 8)[0]
            if data[:8] != b'SPCRUN01' or len(data) != 16+40*count:
                raise ValueError('native trace matrix structure')
            for a, b, token in samples:
                coefficient = -entry(data, count, identities[a], identities[b])
                predicted, printed = coefficient/scale, F(token)
                tolerance = abs(printed)*F(1, 100000)+F(1, 10**12)
                if abs(predicted-printed) > tolerance:
                    raise ValueError('nonzero native printed capacitance scaling mismatch')
                cases.append(dict(a=a, b=b, native_trace_scalar=float(coefficient),
                     printed_token=token, predicted_printed_scalar=float(predicted),
                     absolute_tolerance=float(tolerance)))
        if any(sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError('native capacitance scale input changed')
        save(out/'cases.json', cases)
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(out/'cases.json'): sha(out/'cases.json')},
             nonzero_printed_capacitance_unit_controls_pass=True,
             native_trace_units_per_printed_EXT_unit=str(scale), selected_couplings=len(cases),
             serialization_format='C printf %lg; six significant digits by default',
             full_printed_native_matrix_reconstruction_verified=False,
             physical_RC_qualified=False, release_qualified=False))
        print(json.dumps(dict(trace_units_per_EXT_unit=str(scale), nonzero_controls=len(cases))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'binding', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.binding, args.output)
