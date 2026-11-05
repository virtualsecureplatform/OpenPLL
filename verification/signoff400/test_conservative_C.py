"""Independent Fraction controls for exact C certificates and signed edge evaluation."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import time

from common import ROOT, save, sha
from compiled_charge import execute
from resources import identity, lease


def x87(value):
    value = Fraction(value)
    if not value:
        return bytes(10)
    sign = 0x8000 if value < 0 else 0
    value = abs(value)
    bits = value.numerator.bit_length()
    exponent = value.denominator.bit_length() - 1
    if bits > 64 or value.denominator != 1 << exponent:
        raise ValueError('fixture coefficient must be an exact x87 dyadic')
    return struct.pack('<QH', value.numerator << (64-bits), sign+16383+bits-1-exponent)


def matrix(path, entries):
    with path.open('xb') as stream:
        stream.write(b'SPCRUN01'+struct.pack('<Q', len(entries)))
        for i, j, value in entries:
            stream.write(struct.pack('<Q', i << 32 | j)+x87(value)+x87(max(abs(value), 1))
                         +struct.pack('<Q', 1)+bytes(4))


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         deadline_uptime=deadline, cpu_slots=8, memory_GiB=4, automatic_identical_retry=False))
    sources = [ROOT/'tools/sheet_charge'/name for name in (
        'audit_C_dyadic_residual.cpp', 'certify_conservative_C.cpp',
        'evaluate_C_edge_operator.cpp', 'C_edge_operator.hpp', 'sparse_runs_v2.hpp')]
    sources += [ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in sources}
    results = []
    try:
        with lease(8, 4, deadline):
            binaries = {}
            for name in ('audit_C_dyadic_residual', 'certify_conservative_C', 'evaluate_C_edge_operator'):
                binary = output/name
                execute(['g++', '-std=c++20', '-O3', '-fopenmp', '-fno-fast-math',
                         '-ffp-contract=off', ROOT/f'tools/sheet_charge/{name}.cpp',
                         '-lgmpxx', '-lgmp', '-o', binary], output/f'{name}.build.log', deadline, 4)
                binaries[name] = binary
            rng = random.Random(400)
            trials = [
                ('zero', 3, []),
                ('cancelled', 3, [(1, 1, Fraction((1 << 64)-1, 1 << 64)),
                                   (1, 2, Fraction(-1)), (2, 2, Fraction(1))]),
                ('signed_indefinite', 2, [(0, 0, Fraction(-1)), (0, 1, Fraction(1)), (1, 1, Fraction(-1))]),
                ('needs_large_correction', 2, [(0, 0, Fraction(2)), (0, 1, Fraction(-1)), (1, 1, Fraction(1))]),
            ]
            for n in (2, 7, 31):
                entries = [(i, j, Fraction(rng.randint(-1024, 1024), 1 << rng.randrange(0, 30)))
                           for i in range(n) for j in range(i, n) if rng.random() < .6]
                trials.append((f'random_{n}', n, entries))
            for label, n, entries in trials:
                folder = output/label
                folder.mkdir()
                path = folder/'matrix.bin'
                matrix(path, entries)
                dense = [[Fraction(0) for _ in range(n)] for _ in range(n)]
                for i, j, v in entries:
                    dense[i][j] = dense[j][i] = v
                for name in ('audit_C_dyadic_residual', 'certify_conservative_C'):
                    cfg, report, rows = (folder/(name+suffix) for suffix in ('.json', '.report.json', '.rows.jsonl'))
                    save(cfg, dict(matrix=str(path), node_count=n, deadline_uptime=deadline,
                                   row_certificate=str(rows), report=str(report)))
                    execute([binaries[name], cfg], folder/(name+'.log'), deadline, 4)
                    found = json.loads(report.read_text())
                    quantum = Fraction(2)**found['common_binary_quantum_exponent']
                    observed = [json.loads(line) for line in rows.read_text().splitlines()]
                    assert len(observed) == n
                    outside = 0
                    for i, row in enumerate(observed):
                        residual = sum(dense[i])
                        assert row['row'] == i
                        assert int(row['residual_integer'])*quantum == residual
                        assert int(row['L1_integer'])*quantum == sum(map(abs, dense[i]))
                        if name == 'certify_conservative_C':
                            corrected = dense[i][i]-residual
                            assert int(row['diagonal_correction_integer'])*quantum == -residual
                            assert int(row['conservative_diagonal_integer'])*quantum == corrected
                            bound = Fraction(1e-8)+Fraction(2e-12)*max(abs(dense[i][i]), abs(corrected))
                            outside += abs(residual) > bound
                    if name == 'certify_conservative_C':
                        assert found['rows_outside_coefficient_tolerance'] == outside
                        assert found['all_corrections_within_existing_coefficient_tolerance'] == (outside == 0)
                for mode in ('pattern', 'constant'):
                    voltage = [Fraction((i*7)%13, 8) for i in range(n)] if mode == 'pattern' else [Fraction(3, 8)]*n
                    expected = [sum(-dense[i][j]*(voltage[i]-voltage[j]) for j in range(n) if i != j)
                                for i in range(n)]
                    cfg, report = folder/(mode+'.json'), folder/(mode+'.report.json')
                    save(cfg, dict(matrix=str(path), node_count=n, maximum_adjacency_bytes=1024**3,
                                   threads=[1, 4, 8], vector_mode='explicit', voltage=list(map(float, voltage)),
                                   deadline_uptime=deadline, report=str(report)))
                    execute([binaries['evaluate_C_edge_operator'], cfg], folder/(mode+'.log'), deadline, 4)
                    found = json.loads(report.read_text())
                    assert found['currents'] == list(map(float, expected))
                    assert found['all_requested_thread_vectors_bit_identical']
                    assert not found['full_matrix_passivity_verified']
                results.append(dict(fixture=label, independent_fraction_rows_and_vectors_match=True))
            # Truncation, trailing garbage, and a genuinely out-of-range row must all be rejected.
            for label, data in (
                ('truncated', (output/'cancelled/matrix.bin').read_bytes()[:-1]),
                ('trailing', (output/'cancelled/matrix.bin').read_bytes()+b'x'),
                ('bounds', (output/'cancelled/matrix.bin').read_bytes()),
            ):
                path = output/(label+'.bin'); path.write_bytes(data)
                for name, binary in binaries.items():
                    cfg = output/(label+'_'+name+'.json')
                    save(cfg, dict(matrix=str(path), node_count=1 if label=='bounds' else 3,
                         deadline_uptime=deadline, row_certificate=str(output/'invalid.rows'),
                         report=str(output/'invalid.report'), maximum_adjacency_bytes=1024**3,
                         threads=[1], vector_mode='explicit', voltage=[0, 0, 0]))
                    failed = subprocess.run([str(binary), str(cfg)], capture_output=True, text=True, timeout=30)
                    save(output/(label+'_'+name+'.result.json'), dict(returncode=failed.returncode, stderr=failed.stderr))
                    assert failed.returncode != 0, (label, name)
            if any(sha(p) != h for p, h in pins.items()):
                raise ValueError('control sources changed')
            artifacts = {str(p): sha(p) for p in output.rglob('*') if p.is_file()}
            save(output/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=results,
                 independent_exact_C_auditor_controls_pass=True,
                 conservative_C_coefficient_certificate_controls_pass=True,
                 signed_C_edge_operator_controls_pass=True, threads_checked=[1, 4, 8],
                 malformed_inputs_rejected=True, full_matrix_passivity_verified=False,
                 physical_RC_qualified=False, release_qualified=False))
            save(output/'status.json', dict(state='independent_C_controls_complete', release_qualified=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_promotion', reason=repr(error), release_qualified=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output.resolve())
