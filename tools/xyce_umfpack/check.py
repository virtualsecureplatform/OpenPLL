#!/usr/bin/env python3
"""Check KLU/UMFPACK agreement on a connected nonlinear diode/RC transient.

Run inside the release CAD image. This exercises the diode charge seam and MPI
matrix gathering/scattering, including every ladder voltage and source current.
It is a backend control, not PLL or release qualification.
"""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import lease


def read_table(path, columns):
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) != columns + 1 or not fields[0].isdigit():
            continue
        if int(fields[0]) != len(rows):
            raise ValueError('ordered sample indices required')
        values = tuple(map(float, fields[1:]))
        if not all(map(math.isfinite, values)):
            raise ValueError('nonfinite waveform value')
        if rows and values[0] <= rows[-1][0]:
            raise ValueError('strictly increasing sample time required')
        rows.append(values)
    if len(rows) < 2 or rows[0][0] != 0 or abs(rows[-1][0] - 5e-9) > 1e-20:
        raise ValueError('complete 0..5 ns waveform required')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cpus', default='0,1,2,3')
    parser.add_argument('--solver-threads', type=int, choices=(1,4,8), default=1)
    parser.add_argument('--wall-limit-s', default=120, type=int)
    parser.add_argument('--experimental-checked-reuse', action='store_true',
                        help='Also require one/four-rank reuse agreement, reuse hits and zero DC reuse')
    parser.add_argument('--extra-ranks', type=int, choices=(8, 16, 32),
                        help='Also check a larger MPI count; provide that many CPU IDs')
    parser.add_argument('--pin-ranks', action='store_true',
                        help='Pin each single-host OpenMPI rank to one selected CPU')
    parser.add_argument('--distribution-strategy', type=int, choices=(0,2), default=0,
                        help='Xyce device distribution: default or per-device-type balanced')
    parser.add_argument('--hierarchical-mos', action='store_true',
                        help='Exercise nested MOS wrappers as well as the diode/RC ladder')
    args = parser.parse_args()
    cpus = {int(value) for value in args.cpus.split(',')}
    capacity = args.extra_ranks or 4
    if len(cpus) != capacity * args.solver_threads or not cpus <= set(range(32)) or args.wall_limit_s <= 0:
        parser.error('CPUs must equal maximum MPI ranks times solver threads, within 0..31; positive cap required')
    if args.pin_ranks and args.solver_threads != 1:
        parser.error('individual rank pinning requires one solver thread')
    binary = args.binary.resolve(); out = args.output.resolve()
    if not binary.is_file():
        parser.error('simulator binary does not exist')
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + args.wall_limit_s
    os.sched_setaffinity(0, cpus)
    os.environ.update(OMP_NUM_THREADS=str(args.solver_threads), OMP_THREAD_LIMIT=str(args.solver_threads), OPENBLAS_NUM_THREADS='1')
    nodes = ['node', *[f'n{i}' for i in range(128)]]
    vectors = [*[f'V({name})' for name in nodes], 'I(VDRV)']
    # The deliberately different bottom/sidewall junction parameters exercise
    # the charge offset repaired in both native diode implementation paths.
    circuit = ('* Connected diode and RC backend control; no PDK required.\n'
               '.model DSW D IS=1e-14 N=1 RS=0 CJ=1p M=.44 VJ=.729\n'
               '+ CJSW=.25p MJSW=.2 PHP=.2 FC=.5 FCS=.5 TNOM=27\n'
               'VDRV drive 0 PWL(0 0 1n 0 2n -.5 3n -.5 4n 0 5n 0)\n'
               'RDRV drive node 50\nDTEST 0 node DSW AREA=1 PJ=1\n')
    circuit += f'.options dist strategy={args.distribution_strategy}\n'
    if args.hierarchical_mos:
        circuit += ('.model NCTRL NMOS LEVEL=1 VTO=.45 KP=1m LAMBDA=.02\n'
                    '.subckt MOSCTRL drain\nMCTRL drain 0 0 0 NCTRL L=1u W=1u\n.ends MOSCTRL\n')
        for i in range(128):
            circuit += f'XMOSCTRL{i} n{i} MOSCTRL\n'
    for i in range(128):
        circuit += f'Rmesh{i} ' + ('node' if i == 0 else f'n{i-1}') + f' n{i} 10000\nCmesh{i} n{i} 0 1f\n'
    circuit += ('.tran 5p 5n 0 5p\n.options device temp=27\n'
                '.options nonlin reltol=1e-6 abstol=1e-12\n'
                '.options timeint reltol=1e-6 abstol=1e-12\n')
    results, tables = [], []
    cases = [('klu4', 4, 'klu'), ('umfpack1', 1, 'umfpack'), ('umfpack4', 4, 'umfpack')]
    if args.experimental_checked_reuse:
        cases += [('reuse1', 1, 'umfpack_reuse'), ('reuse4', 4, 'umfpack_reuse')]
    if args.extra_ranks:
        cases.append((f'umfpack{args.extra_ranks}', args.extra_ranks, 'umfpack'))
        if args.experimental_checked_reuse:
            cases.append((f'reuse{args.extra_ranks}', args.extra_ranks, 'umfpack_reuse'))
    for name, ranks, solver in cases:
        case = out / name; case.mkdir(); trace = case / 'trace.prn'; deck = case / 'control.spice'
        deck.write_text(circuit + f'.PRINT TRAN FORMAT=STD PRECISION=17 FILE={trace} ' + ' '.join(vectors) + '\n.end\n')
        command = ['/usr/bin/mpirun', '--bind-to', 'none', '-np', str(ranks),
                   binary, '-linsolv', solver, deck]
        if args.pin_ranks:
            command[5:5] = [sys.executable, str(Path(__file__).with_name('rank_exec.py')),
                            '--cpus', ','.join(map(str, sorted(cpus))), '--']
        with lease(len(cpus), 8, deadline):
            execute(command, case / 'native.log', deadline, 8)
        table = read_table(trace, 1 + len(vectors)); tables.append(table)
        result = dict(name=name, MPI_ranks=ranks, points=len(table), command=list(map(str, command)))
        if solver == 'umfpack_reuse':
            stats = re.findall(r'calls=(\d+) numeric=(\d+) symbolic=(\d+) failures=(\d+) reuse_attempts=(\d+) reuse_accepted=(\d+) exact_reuse=(\d+) refinement_solves=(\d+) DC_reuse=(\d+)', (case / 'native.log').read_text())
            if not stats or any(int(row[-1]) != 0 for row in stats):
                raise ValueError('Reuse statistics missing or DC reuse occurred')
            hits = sum(int(row[5]) + int(row[6]) for row in stats)
            if hits == 0:
                raise ValueError('Native control did not exercise reuse')
            result.update(reuse_hits=hits, DC_reuse_hits=0, adapter_statistics=stats)
        results.append(result)
    reference = tables[0]
    for rows, result in zip(tables, results):
        if len(rows) != len(reference):
            raise ValueError('native sampling grids differ')
        dt = max(abs(a[0] - b[0]) for a, b in zip(reference, rows))
        dv = max(abs(a[i] - b[i]) for a, b in zip(reference, rows) for i in range(1, 1 + len(nodes)))
        di = max(abs(a[-1] - b[-1]) for a, b in zip(reference, rows))
        result.update(max_time_grid_difference_s=dt, max_voltage_difference_V=dv, max_source_current_difference_A=di)
        if dt > 1e-20 or dv > 1e-8 or di > 1e-12:
            raise ValueError('backend waveform agreement failed: ' + repr(result))
    report = dict(all_native_controls_complete_and_agree=True, results=results,
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  observed_voltage_vectors=len(nodes), observed_current_vectors=1,
                  experimental_checked_reuse=args.experimental_checked_reuse,
                  solver_threads=args.solver_threads, reserved_CPUs=sorted(cpus),
                  extra_MPI_ranks=args.extra_ranks, ranks_pinned_to_individual_CPUs=args.pin_ranks,
                  distribution_strategy=args.distribution_strategy, hierarchical_MOS_control=args.hierarchical_mos,
                  full_PLL_qualified=False, release_ready=False)
    (out / 'assessment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'KLU and UMFPACK controls agree through {capacity} MPI ranks.')


if __name__ == '__main__':
    main()
