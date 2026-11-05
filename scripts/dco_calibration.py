#!/usr/bin/env python3
"""Resumable extracted-DCO band screening and numerical calibration.

Screen all coarse bands first. Qualify a selected band with separate baseline,
tighter-tolerance, half-step and longer-settling runs. Outputs are functional
frequency models, never physical-noise qualification.
"""
import argparse
import itertools
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys

from pll_verification import load_spec
from spice_dco_postlayout import read_waveform_points, threshold_crossings


def measure(path, start_ns, stop_ns, vdd, min_periods=8):
    points = read_waveform_points(path)
    if not points or any(not math.isfinite(t) or not math.isfinite(v) for t, v in points):
        raise ValueError('missing or nonfinite waveform')
    if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError('nonmonotonic waveform time')
    if points[-1][0] < stop_ns * 1e-9 * (1 - 1e-7):
        raise ValueError('incomplete transient')
    edges = threshold_crossings(points, vdd / 2, 'rise', start_ns * 1e-9)
    edges = [t for t in edges if t <= stop_ns * 1e-9]
    if len(edges) < min_periods + 1:
        raise ValueError(f'need at least {min_periods} measured periods')
    middle = (len(edges) - 1) // 2
    frequency = (len(edges) - 1) / (edges[-1] - edges[0]) * 1e-6
    first = middle / (edges[middle] - edges[0]) * 1e-6
    last = (len(edges) - 1 - middle) / (edges[-1] - edges[middle]) * 1e-6
    return dict(mhz=frequency, periods=len(edges)-1,
                half_window_difference_mhz=abs(first-last),
                first_edge_ns=edges[0]*1e9, last_edge_ns=edges[-1]*1e9)


def validate_sample_values(samples, target_mhz):
    if not math.isfinite(target_mhz) or target_mhz <= 0:
        raise ValueError('target frequency must be finite and positive')
    for sample in samples:
        frequency = sample['mhz']
        drift = sample['half_window_difference_mhz']
        if (not math.isfinite(frequency) or frequency <= 0
                or not math.isfinite(drift) or drift < 0):
            raise ValueError('calibration samples must have finite positive frequency and nonnegative drift')


def assess(samples, target_mhz, spec=None):
    """All variants must resolve adjacent-code spacing, not just target ppm."""
    spec = spec or load_spec()
    variants = ('baseline', 'tolerance', 'step', 'settling')
    if set(samples) != set(variants):
        raise ValueError('four independent convergence variants required')
    codes = sorted(samples['baseline'])
    if any(sorted(samples[v]) != codes for v in variants) or len(codes) < 3:
        raise ValueError('matching calibration code sets required')
    validate_sample_values((sample for v in variants for sample in samples[v].values()), target_mhz)
    reference = samples['settling']
    points = [dict(code=c, mhz=reference[c]['mhz']) for c in codes]
    comparisons = []
    for i, code in enumerate(codes):
        neighbors = codes[max(0, i-1):i] + codes[i+1:i+2]
        # Adjacent codes are mandatory for a local fine-LSB qualification.
        adjacent = [c for c in neighbors if abs(c-code) == 1]
        if not adjacent:
            raise ValueError(f'code {code} needs a measured adjacent code')
        lsb = min(abs(reference[c]['mhz']-reference[code]['mhz']) for c in adjacent)
        limit = min(target_mhz*spec['calibration_error_ppm']*1e-6,
                    lsb*spec['calibration_error_local_lsb'])
        frequencies = [samples[v][code]['mhz'] for v in variants]
        difference = max(frequencies)-min(frequencies)
        settling = max(samples[v][code]['half_window_difference_mhz'] for v in variants)
        comparisons.append(dict(code=code, local_lsb_mhz=lsb, limit_mhz=limit,
                                variant_spread_mhz=difference, settling_difference_mhz=settling,
                                passed=limit > 0 and difference <= limit and settling <= limit))
    return dict(points=points, comparisons=comparisons,
                convergence_passed=all(c['passed'] for c in comparisons))


def assess_interpolation(reference, holdouts, anchors, target_mhz, spec=None):
    """Check every legal fine code against linear interpolation between anchors."""
    spec = spec or load_spec()
    low, high = spec['fine_code_min'], spec['fine_code_max']
    codes = set(range(low, high + 1))
    if (not set(anchors) <= set(reference) or
            set(reference) | set(holdouts) != codes or
            set(reference) & set(holdouts)):
        raise ValueError('interpolation sweep must cover every fine code exactly once')
    actual = {**reference, **holdouts}
    validate_sample_values(actual.values(), target_mhz)
    rows = []
    for code in range(low, high + 1):
        left = max(anchor for anchor in anchors if anchor <= code)
        right = min(anchor for anchor in anchors if anchor >= code)
        prediction = (reference[left]['mhz'] if left == right else
                      reference[left]['mhz'] +
                      (reference[right]['mhz'] - reference[left]['mhz']) *
                      (code - left) / (right - left))
        neighbors = [neighbor for neighbor in (code - 1, code + 1)
                     if low <= neighbor <= high]
        lsb = min(abs(actual[neighbor]['mhz'] - actual[code]['mhz'])
                  for neighbor in neighbors)
        limit = min(target_mhz * spec['calibration_error_ppm'] * 1e-6,
                    lsb * spec['calibration_error_local_lsb'])
        error = abs(prediction - actual[code]['mhz'])
        settling = actual[code]['half_window_difference_mhz']
        monotonic = all(actual[neighbor]['mhz'] < actual[code]['mhz']
                        for neighbor in neighbors if neighbor < code) and all(
                            actual[code]['mhz'] < actual[neighbor]['mhz']
                            for neighbor in neighbors if neighbor > code)
        rows.append(dict(code=code, measured_mhz=actual[code]['mhz'],
                         predicted_mhz=prediction, error_mhz=error,
                         local_lsb_mhz=lsb, limit_mhz=limit,
                         settling_difference_mhz=settling,
                         passed=limit > 0 and monotonic and error <= limit
                                and settling <= limit))
    return dict(interpolation_comparisons=rows,
                interpolation_validated=all(row['passed'] for row in rows))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['screen', 'qualify'])
    p.add_argument('--xyce', type=Path, required=True)
    p.add_argument('--xyce-linear-solver', choices=['default', 'KLU'], default='default')
    p.add_argument('--pdk-root', type=Path, required=True)
    p.add_argument('--rcx-netlist', type=Path, required=True)
    p.add_argument('--subckt-name', default='IntegerPLL_DCO_EINVP_COARSE')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--coarse', type=int, nargs='+')
    p.add_argument('--mode-mhz', type=int, choices=[100,250,300,400,450], default=100)
    p.add_argument('--target-code', type=int,
                   help='Selected fine code to qualify against --mode-mhz')
    p.add_argument('--validate-interpolation', action='store_true',
                   help='Measure every remaining fine code and validate the sparse curve')
    p.add_argument('--pvt-grid', action='store_true')
    p.add_argument('--corner', choices=['tt','ff','ss','sf','fs'], default='tt')
    p.add_argument('--vdd', type=float, default=1.8)
    p.add_argument('--temperature-c', type=float, default=27)
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--mpi-ranks', type=int, default=1)
    p.add_argument('--settle-ns', type=float, default=100)
    p.add_argument('--window-ns', type=float, default=200)
    p.add_argument('--max-step-ps', type=float, default=10)
    p.add_argument('--reltol', type=float, default=1e-5)
    p.add_argument('--abstol', type=float, default=1e-9)
    a = p.parse_args()
    if any(not math.isfinite(x) or x <= 0 for x in
           [a.vdd,a.jobs,a.mpi_ranks,a.settle_ns,a.window_ns,a.max_step_ps,a.reltol,a.abstol]):
        p.error('simulation settings must be finite and positive')
    if not math.isfinite(a.temperature_c) or a.temperature_c <= -273.15:
        p.error('invalid temperature')
    if a.stage == 'qualify' and (not a.coarse or len(a.coarse) != 1):
        p.error('qualify requires exactly one --coarse band')
    if not a.xyce.is_file():
        p.error(f'Xyce binary is missing: {a.xyce}')
    coarse = a.coarse if a.coarse is not None else list(range(48))
    if any(c < 0 or c > 47 for c in coarse): p.error('coarse bands must be 0..47')
    spec = load_spec()
    low, high = spec['fine_code_min'], spec['fine_code_max']
    if a.stage == 'qualify' and (a.target_code is None or
                                 not low <= a.target_code <= high):
        p.error(f'qualify requires --target-code in {low}..{high}')
    if a.stage != 'qualify' and a.validate_interpolation:
        p.error('--validate-interpolation requires qualify')
    pvt = list(itertools.product(spec['corners'], spec['voltages'], spec['temperatures_c'])) if a.pvt_grid else [(a.corner,a.vdd,a.temperature_c)]
    # Sparse interpolation anchors with measured local spacing at every anchor.
    anchors = sorted(set(range(low, high + 1, 16)) | {low, high})
    codes = [low, (low + high + 1) // 2, high] if a.stage == 'screen' else sorted(
        set(anchors) | {c + 1 if c < high else c - 1 for c in anchors}
        | {c for c in (a.target_code - 1, a.target_code, a.target_code + 1)
           if low <= c <= high})
    interpolation_codes = sorted(set(range(low, high + 1)) - set(codes))
    settings = dict(baseline=(a.reltol,a.abstol,a.max_step_ps,a.settle_ns,a.window_ns))
    if a.stage == 'qualify':
        settings.update(tolerance=(a.reltol/10,a.abstol/10,a.max_step_ps,a.settle_ns,a.window_ns),
                        step=(a.reltol,a.abstol,a.max_step_ps/2,a.settle_ns,a.window_ns),
                        settling=(a.reltol/10,a.abstol/10,a.max_step_ps/2,a.settle_ns*2,a.window_ns*2))
        if a.validate_interpolation and interpolation_codes:
            settings['interpolation'] = settings['settling']
    a.output.mkdir(parents=True,exist_ok=True)
    reports = []
    failed = False
    for corner,vdd,temp in pvt:
        directory = a.output/f'{corner}_{vdd:g}V_{temp:g}C'
        samples = {c:{} for c in coarse}
        sources = {}
        errors = []
        for variant,(rel,ab,step,start,window) in settings.items():
            variant_codes = interpolation_codes if variant == 'interpolation' else codes
            run = directory/variant
            run.mkdir(parents=True,exist_ok=True)
            xyce_command = shlex.quote(str(a.xyce.resolve()))
            if a.xyce_linear_solver != 'default':
                xyce_command += f' -linsolv {a.xyce_linear_solver}'
            cmd = [sys.executable,str(Path(__file__).with_name('spice_dco_postlayout.py')),
                   '--simulator','xyce','--xyce',xyce_command,
                   '--xyce-mpi-procs',str(a.mpi_ranks),'--pdk-root',str(a.pdk_root.resolve()),
                   '--rcx-netlist',str(a.rcx_netlist.resolve()),'--subckt-name',a.subckt_name,
                   '--coarse-codes',','.join(map(str,coarse)),'--codes',','.join(map(str,variant_codes)),
                   '--corner',corner,'--vdd',str(vdd),'--temperature-c',str(temp),
                   '--meas-start-ns',str(start),'--sim-time-ns',str(start+window),
                   '--step-ps',str(step),'--max-step-ps',str(step),'--xyce-reltol',str(rel),
                   '--xyce-abstol',str(ab),'--jobs',str(a.jobs),'--resume','--build-dir',str(run.resolve())]
            print(f'{corner} {vdd:g}V {temp:g}C {variant}',flush=True)
            with (run/'campaign.log').open('w') as log:
                result = subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode: errors.append(f'{variant}: simulator runner exited {result.returncode}')
            provenance = run/'provenance.json'
            if provenance.exists(): sources[variant] = json.loads(provenance.read_text())
            for band in coarse:
                samples[band][variant] = {}
                for code in variant_codes:
                    base = run/f'dco_postlayout_{corner}_coarse_{band:02d}_code_{code:03d}'
                    try:
                        sidecar = json.loads(base.with_suffix('.provenance.json').read_text())
                        if not sidecar.get('completed'): raise ValueError('run did not complete successfully')
                        samples[band][variant][code] = measure(base.with_suffix('.prn'),start,start+window,vdd)
                    except (OSError,ValueError) as error:
                        errors.append(f'{variant}/C{band}/{code}: {error}')
        report = dict(stage=a.stage,corner=corner,vdd=vdd,temperature_c=temp,
                      simulator='Xyce',solver=a.xyce_linear_solver,subckt_name=a.subckt_name,
                      errors=errors,samples=samples,provenance=sources,
                      evidence='deterministic_frequency_only',
                      interpolation_validated=False, convergence_passed=False)
        if a.stage == 'qualify' and not errors:
            report.update(assess({variant: samples[coarse[0]][variant]
                                  for variant in ('baseline','tolerance','step','settling')},
                                 a.mode_mhz,spec))
            if a.validate_interpolation:
                report.update(assess_interpolation(
                    samples[coarse[0]]['settling'],
                    samples[coarse[0]].get('interpolation', {}),
                    anchors, a.mode_mhz, spec))
            measured = samples[coarse[0]]['settling'][a.target_code]
            target_error_ppm = abs(measured['mhz'] / a.mode_mhz - 1) * 1e6
            local_codes = [c for c in (a.target_code - 1, a.target_code,
                                       a.target_code + 1) if low <= c <= high]
            target_monotonic_passed = all(
                samples[coarse[0]]['settling'][left]['mhz']
                < samples[coarse[0]]['settling'][right]['mhz']
                for left, right in zip(local_codes, local_codes[1:]))
            report.update(coarse=coarse[0],mode_mhz=a.mode_mhz,
                          target_code=a.target_code,
                          target_frequency_mhz=measured['mhz'],
                          target_frequency_error_ppm=target_error_ppm,
                          target_monotonic_passed=target_monotonic_passed,
                          target_frequency_passed=(
                              target_error_ppm <= spec['frequency_error_ppm']))
            endpoints = [samples[coarse[0]]['settling'][c]['mhz'] for c in [low,high]]
            report['coverage_passed'] = min(endpoints) <= a.mode_mhz <= max(endpoints)
            failed |= (not report['convergence_passed'] or not report['coverage_passed']
                       or not report['target_frequency_passed']
                       or not report['target_monotonic_passed']
                       or not report['interpolation_validated'])
        elif a.stage == 'screen':
            report['candidate_bands'] = {str(mode): [c for c in coarse
                if low in samples[c]['baseline'] and high in samples[c]['baseline']
                and min(samples[c]['baseline'][k]['mhz'] for k in [low,high]) <= mode
                <= max(samples[c]['baseline'][k]['mhz'] for k in [low,high])]
                for mode in spec['modes_mhz']}
            report['convergence_passed'] = False
        failed |= bool(errors)
        destination = directory/'calibration.json'
        destination.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        reports.append(str(destination.resolve()))
        (a.output/'campaign.json').write_text(json.dumps(dict(stage=a.stage,reports=reports,failed=failed),indent=2)+'\n')
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
