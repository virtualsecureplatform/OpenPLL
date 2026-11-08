#!/usr/bin/env python3
"""Build an isolated MPI Xyce UMFPACK backend inside the release CAD image.

Example (from the repository root, inside the image):
  python3 tools/xyce_umfpack/build.py --output build/tools/xyce_umfpack

The stock simulator, PDK, and image sources are read only. The output directory
must be new. This also applies the independently validated diode sidewall charge
correction used by the PLL comparisons. A build alone grants no qualification.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import identity, lease


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def archive_members(path):
    """Compare member contents, excluding the ar symbol index and metadata."""
    members, longnames = {}, b''
    with Path(path).open('rb') as stream:
        if stream.read(8) != b'!<arch>\n':
            raise ValueError('GNU archive required')
        while True:
            header = stream.read(60)
            if not header:
                return members
            if len(header) != 60 or header[58:] != b'`\n':
                raise ValueError('invalid archive header')
            size = int(header[48:58]); name = header[:16].decode().strip()
            data = stream.read(size)
            if len(data) != size:
                raise ValueError('truncated archive')
            if size % 2:
                stream.read(1)
            if name == '//':
                longnames = data
                continue
            if name in ('/', '/SYM64/'):
                continue
            if name.startswith('/') and name[1:].isdigit():
                offset = int(name[1:])
                name = longnames[offset:longnames.index(b'/\n', offset)].decode()
            else:
                name = name.removesuffix('/')
            if name in members:
                raise ValueError('duplicate archive member: ' + name)
            members[name] = hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cpus', default='0,1', help='CPU IDs within 0..31')
    parser.add_argument('--wall-limit-s', default=300, type=int)
    parser.add_argument('--timestep-diagnostics', action='store_true',
                        help='Trace TRAP timestep decisions every 100 steps without changing them')
    parser.add_argument('--experimental-adaptive-step-growth', action='store_true',
                        help='Opt-in TRAP growth from 1.25x using the existing error estimate; unqualified')
    parser.add_argument('--experimental-checked-reuse', action='store_true',
                        help='Build the opt-in, not yet full-PLL-qualified factor reuse backend')
    parser.add_argument('--reuse-policy', choices=('conservative', 'krylov', 'krylov-mixed', 'krylov-csr', 'krylov-csr-double', 'parallel-residual', 'adapter-timing', 'cached-conversion', 'value-gather'),
                        default='conservative', help='Policy for the experimental reuse backend')
    args = parser.parse_args()
    if args.reuse_policy != 'conservative' and not args.experimental_checked_reuse:
        parser.error('--reuse-policy requires --experimental-checked-reuse')
    cpus = {int(value) for value in args.cpus.split(',')}
    if not cpus or not cpus <= set(range(32)) or args.wall_limit_s <= 0:
        parser.error('positive wall limit and CPU IDs within 0..31 required')
    out = args.output.resolve()
    source = Path('/opt/Xyce/src')
    build = Path('/opt/xyce-build/src')
    archive = build / 'libxyce.a'
    flags = build / 'CMakeFiles/XyceLib.dir/flags.make'
    link = build / 'CMakeFiles/Xyce.dir/link.txt'
    diode = source / 'DeviceModelPKG/OpenModels/N_DEV_Diode.C'
    factory = source / 'LinearAlgebraServicesPKG/N_LAS_TranSolverFactory.C'
    header = Path(__file__).with_name('N_LAS_OpenPLLUMFPACKSolver.h')
    nls = source / 'NonlinearSolverPKG/N_NLS_NonLinearSolver.C'
    one_step = source / 'TimeIntegrationPKG/N_TIA_OneStep.C'
    extra_headers = []
    if args.experimental_checked_reuse:
        folder = {'conservative': 'experimental', 'krylov': 'experimental_krylov',
                  'krylov-mixed': 'experimental_krylov_mixed',
                  'krylov-csr': 'experimental_krylov_csr',
                  'krylov-csr-double': 'experimental_krylov_csr_double',
                  'parallel-residual': 'experimental_parallel_residual',
                  'adapter-timing': 'experimental_adapter_timing',
                  'cached-conversion': 'experimental_cached_conversion',
                  'value-gather': 'experimental_value_gather'}[args.reuse_policy]
        header = Path(__file__).with_name(folder) / header.name
        extra_headers = [header.with_name('CheckedUMFPACK.h')]
    stock = Path('/opt/xyce/bin/Xyce')
    libraries = [Path('/usr/lib/x86_64-linux-gnu/libumfpack.so.6'),
                 Path('/usr/lib/x86_64-linux-gnu/libblas.so.3')]
    inputs = [Path(__file__).resolve(), header, diode, factory, archive,
              flags, link, stock, *libraries]
    if args.timestep_diagnostics or args.experimental_adaptive_step_growth:
        inputs.append(one_step)
    if args.experimental_checked_reuse:
        inputs += [nls, *extra_headers]
    if not all(p.is_file() for p in inputs):
        raise RuntimeError('Run inside the pinned OpenPLL release CAD image; required source/build inputs are missing')
    out.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + '\n')

    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + args.wall_limit_s
    save('owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         deadline_uptime=deadline, cpus=sorted(cpus), memory_GiB=16,
         old_checkpoint_modified=False))
    save('status.json', dict(state='preparing', release_ready=False))
    try:
        pins = {str(p): digest(p) for p in inputs}
        for item in [header, *extra_headers]:
            (out / item.name).write_bytes(item.read_bytes())
        original = diode.read_text()
        old = 'Qd += CzeroSW * tF1 +'
        new = ('Qd += CzeroSW * (tJctSWPot * (1.0 - exp((1.0 - MJSW) * '
               'log(1.0 - tDepSWCap / tJctSWPot))) / (1.0 - MJSW)) +')
        if original.count(old) != 2:
            raise ValueError('Expected both pinned diode charge-offset sites')
        changed = original.replace(old, new)
        (out / diode.name).write_text(changed)
        (out / 'diode.patch').write_text(''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True),
            fromfile='stock/' + diode.name, tofile='corrected/' + diode.name)))
        original = factory.read_text()
        include = '#include <N_LAS_AmesosSolver.h>'
        branch = '  else if( type == "IR" )'
        if original.count(include) != 1 or original.count(branch) != 1:
            raise ValueError('Pinned Xyce factory layout changed')
        changed = original.replace(include, include + '\n#include <N_LAS_OpenPLLUMFPACKSolver.h>')
        if args.experimental_checked_reuse:
            backend_branch = ('  else if( type == "UMFPACK" || type == "UMFPACK_REUSE" )\n'
                              '    return new OpenPLLUMFPACKSolver(problem, options, type == "UMFPACK_REUSE");\n')
        else:
            backend_branch = ('  else if( type == "UMFPACK" )\n'
                              '    return new OpenPLLUMFPACKSolver(problem, options);\n')
        changed = changed.replace(branch, backend_branch + branch)
        (out / factory.name).write_text(changed)
        (out / 'factory.patch').write_text(''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True),
            fromfile='stock/' + factory.name, tofile='UMFPACK/' + factory.name)))
        sources = [diode, factory]
        if args.timestep_diagnostics or args.experimental_adaptive_step_growth:
            original_step = one_step.read_text()
            changed_step = original_step
            anchor = '\n  newTimeStep_ = std::max(newTimeStep_, sec.minTimeStep);'
            if original_step.count(anchor) != 1:
                raise ValueError('Pinned TRAP accepted-step layout changed')
            trace = '''  if (sec.numberOfSteps_ % 100 == 0)
  {
    Xyce::lout() << "OpenPLL timestep: time=" << sec.currentTime
      << " step=" << sec.currentTimeStep << " order=" << sec.currentOrder_
      << " error_ratio=" << sec.estOverTol_
      << " proposed=" << newTimeStep_ << " maximum=" << sec.maxTimeStep
      << " minimum=" << sec.minTimeStep << " stop=" << sec.stopTime
      << " nonlinear_iterations=" << sec.nIterations << std::endl;
  }
'''
            if args.timestep_diagnostics:
                changed_step = changed_step.replace(anchor, '\n' + trace + anchor)
            if args.experimental_adaptive_step_growth:
                old_growth = ('    if (rr >= sec.r_hincr_test_)\n'
                              '    {\n'
                              '      rr = sec.r_hincr_;\n'
                              '      newTimeStep_ = rr*sec.currentTimeStep;\n'
                              '    }')
                new_growth = ('    if (rr >= 1.25)\n'
                              '    {\n'
                              '      rr = std::min(rr, sec.r_hincr_);\n'
                              '      newTimeStep_ = rr*sec.currentTimeStep;\n'
                              '    }')
                if changed_step.count(old_growth) != 1:
                    raise ValueError('Pinned TRAP growth controller layout changed')
                changed_step = changed_step.replace(old_growth, new_growth)
            (out / one_step.name).write_text(changed_step)
            (out / 'timestep_diagnostics.patch').write_text(''.join(difflib.unified_diff(
                original_step.splitlines(True), changed_step.splitlines(True),
                fromfile='stock/' + one_step.name, tofile='diagnostic/' + one_step.name)))
            sources.append(one_step)
        if args.experimental_checked_reuse:
            original_nls = nls.read_text()
            include_nls = '#include <N_LAS_Solver.h>'
            context = '  lasSolverRCPtr_->setNewtonIter( getNumIterations() );'
            if original_nls.count(include_nls) != 1 or original_nls.count(context) != 1:
                raise ValueError('Pinned nonlinear solver layout changed')
            changed_nls = original_nls.replace(include_nls, include_nls + '\n#include <N_LAS_OpenPLLUMFPACKSolver.h>')
            changed_nls = changed_nls.replace(context, context +
                '\n  if (auto *umf = dynamic_cast<Linear::OpenPLLUMFPACKSolver*>(lasSolverRCPtr_.get()))'
                '\n    umf->setTransientContext(getAnalysisManager().getTransientFlag() && !getAnalysisManager().getDCOPFlag());')
            (out / nls.name).write_text(changed_nls)
            (out / 'NLS_context.patch').write_text(''.join(difflib.unified_diff(
                original_nls.splitlines(True), changed_nls.splitlines(True),
                fromfile='stock/' + nls.name, tofile='checked-reuse/' + nls.name)))
            sources.append(nls)
        compiler_flags = {}
        for line in flags.read_text().splitlines():
            if ' = ' in line:
                key, value = line.split(' = ', 1)
                compiler_flags[key] = shlex.split(value)
        if args.reuse_policy == 'parallel-residual':
            compiler_flags['CXX_FLAGS'].append('-fopenmp')
        objects = [out / (p.name + '.o') for p in sources]
        commands = [['/usr/bin/mpicxx', '-I' + str(out), '-I/usr/include/suitesparse',
                     *compiler_flags['CXX_DEFINES'], *compiler_flags['CXX_INCLUDES'],
                     *compiler_flags['CXX_FLAGS'], '-c', str(out / p.name), '-o', str(obj)]
                    for p, obj in zip(sources, objects)]
        target = out / 'libxyce.a'; binary = out / 'Xyce'
        commands.append(['/usr/bin/ar', 'rcs', str(target), *map(str, objects)])
        command = shlex.split(link.read_text())
        if command.count('libxyce.a') != 1:
            raise ValueError('Unexpected pinned link command')
        command[command.index('libxyce.a')] = str(target)
        command[command.index('-o') + 1] = str(binary)
        command.append('-lumfpack')
        if args.reuse_policy == 'parallel-residual':
            command.append('-fopenmp')
        commands.append(command)
        save('manifest.json', dict(input_sha256=pins, commands=commands,
             timestep_diagnostics=args.timestep_diagnostics,
             experimental_adaptive_step_growth=args.experimental_adaptive_step_growth,
             diode_charge_correction=True, linear_backend='UMFPACK',
             experimental_checked_reuse=args.experimental_checked_reuse,
             experimental_reuse_policy=args.reuse_policy if args.experimental_checked_reuse else None,
             DC_reuse_disabled=args.experimental_checked_reuse,
             stock_inputs_modified=False, qualification_granted=False))
        os.sched_setaffinity(0, cpus)
        os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
        with lease(len(cpus), 16, deadline):
            with archive.open('rb') as src, target.open('xb') as dst:
                import shutil
                shutil.copyfileobj(src, dst, 1024 * 1024)
            os.chdir(build)
            for i, command in enumerate(commands):
                save('status.json', dict(state='building', stage=i, release_ready=False))
                execute(command, out / f'stage_{i}.log', deadline, 16)
            before, after = archive_members(archive), archive_members(target)
            differences = sorted(k for k in before if before[k] != after.get(k))
            if before.keys() != after.keys() or differences != sorted(p.name for p in objects):
                raise ValueError('Unexpected archive changes: ' + repr(differences))
            execute([binary, '-capabilities'], out / 'capabilities.log', deadline, 16)
        for path, expected in pins.items():
            if digest(path) != expected:
                raise RuntimeError('Build input changed: ' + path)
        save('assessment.json', dict(state='isolated_MPI_UMFPACK_backend_built',
             timestep_diagnostics=args.timestep_diagnostics,
             experimental_adaptive_step_growth=args.experimental_adaptive_step_growth,
             input_sha256=pins, changed_archive_members=differences,
             binary_sha256=digest(binary), solver_header_sha256=digest(header),
             experimental_checked_reuse=args.experimental_checked_reuse,
             experimental_reuse_policy=args.reuse_policy if args.experimental_checked_reuse else None,
             diode_fix_normal_and_analytic_paths=True, stock_inputs_modified=False,
             native_validation_required=True, release_ready=False))
        save('status.json', dict(state='built', release_ready=False))
        print(binary)
    except BaseException as error:
        save('status.json', dict(state='stopped', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    main()
