#!/usr/bin/env python3
"""Resumable KLS DCO band screening and numerical calibration.

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


def assess(samples, target_mhz, spec=None):
    """All variants must resolve adjacent-code spacing, not just target ppm."""
    spec = spec or load_spec()
    variants = ('baseline', 'tolerance', 'step', 'settling')
    if set(samples) != set(variants):
        raise ValueError('four independent convergence variants required')
    codes = sorted(samples['baseline'])
    if any(sorted(samples[v]) != codes for v in variants) or len(codes) < 3:
        raise ValueError('matching calibration code sets required')
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['screen', 'qualify'])
    p.add_argument('--xyce', type=Path, required=True)
    p.add_argument('--pdk-root', type=Path, required=True)
    p.add_argument('--rcx-netlist', type=Path, required=True)
    p.add_argument('--subckt-name', default='IntegerPLL_DCO_EINVP_COARSE')
    p.add_argument('--kls-backend', choices=['AUTO','KLS','SERIAL'], default='AUTO')
    p.add_argument('--kls-fresh-factor', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--coarse', type=int, nargs='+')
    p.add_argument('--mode-mhz', type=int, choices=[100,250,300,400,500], default=100)
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
    coarse = a.coarse if a.coarse is not None else list(range(48))
    if any(c < 0 or c > 47 for c in coarse): p.error('coarse bands must be 0..47')
    spec = load_spec()
    pvt = list(itertools.product(spec['corners'], spec['voltages'], spec['temperatures_c'])) if a.pvt_grid else [(a.corner,a.vdd,a.temperature_c)]
    # Sparse interpolation anchors with measured local spacing at every anchor.
    anchors = sorted(set(range(0,256,16)) | {8,247,255})
    codes = [8,128,247] if a.stage == 'screen' else sorted(set(anchors) | {min(c+1,255) if c<255 else 254 for c in anchors})
    settings = dict(baseline=(a.reltol,a.abstol,a.max_step_ps,a.settle_ns,a.window_ns))
    if a.stage == 'qualify':
        settings.update(tolerance=(a.reltol/10,a.abstol/10,a.max_step_ps,a.settle_ns,a.window_ns),
                        step=(a.reltol,a.abstol,a.max_step_ps/2,a.settle_ns,a.window_ns),
                        settling=(a.reltol/10,a.abstol/10,a.max_step_ps/2,a.settle_ns*2,a.window_ns*2))
    a.output.mkdir(parents=True,exist_ok=True)
    reports = []
    failed = False
    for corner,vdd,temp in pvt:
        directory = a.output/f'{corner}_{vdd:g}V_{temp:g}C'
        samples = {c:{} for c in coarse}
        sources = {}
        errors = []
        for variant,(rel,ab,step,start,window) in settings.items():
            run = directory/variant
            run.mkdir(parents=True,exist_ok=True)
            cmd = [sys.executable,str(Path(__file__).with_name('spice_dco_postlayout.py')),
                   '--simulator','xyce','--xyce',shlex.quote(str(a.xyce.resolve()))+' -linsolv KLS',
                   '--xyce-mpi-procs',str(a.mpi_ranks),'--pdk-root',str(a.pdk_root.resolve()),
                   '--rcx-netlist',str(a.rcx_netlist.resolve()),'--subckt-name',a.subckt_name,
                   '--kls-backend',a.kls_backend,
                   '--coarse-codes',','.join(map(str,coarse)),'--codes',','.join(map(str,codes)),
                   '--corner',corner,'--vdd',str(vdd),'--temperature-c',str(temp),
                   '--meas-start-ns',str(start),'--sim-time-ns',str(start+window),
                   '--step-ps',str(step),'--max-step-ps',str(step),'--xyce-reltol',str(rel),
                   '--xyce-abstol',str(ab),'--jobs',str(a.jobs),'--resume','--build-dir',str(run.resolve())]
            print(f'{corner} {vdd:g}V {temp:g}C {variant}',flush=True)
            if a.kls_fresh_factor: cmd.append('--kls-fresh-factor')
            with (run/'campaign.log').open('w') as log:
                result = subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode: errors.append(f'{variant}: simulator runner exited {result.returncode}')
            provenance = run/'provenance.json'
            if provenance.exists(): sources[variant] = json.loads(provenance.read_text())
            for band in coarse:
                samples[band][variant] = {}
                for code in codes:
                    base = run/f'dco_postlayout_{corner}_coarse_{band:02d}_code_{code:03d}'
                    try:
                        sidecar = json.loads(base.with_suffix('.provenance.json').read_text())
                        if not sidecar.get('completed'): raise ValueError('run did not complete successfully')
                        samples[band][variant][code] = measure(base.with_suffix('.prn'),start,start+window,vdd)
                    except (OSError,ValueError) as error:
                        errors.append(f'{variant}/C{band}/{code}: {error}')
        report = dict(stage=a.stage,corner=corner,vdd=vdd,temperature_c=temp,
                      solver='KLS',kls_backend=a.kls_backend,subckt_name=a.subckt_name,
                      kls_fresh_factor=a.kls_fresh_factor,
                      errors=errors,samples=samples,provenance=sources,
                      evidence='deterministic_frequency_only',
                      interpolation_validated=False, convergence_passed=False)
        if a.stage == 'qualify' and not errors:
            report.update(assess(samples[coarse[0]],a.mode_mhz,spec))
            report.update(coarse=coarse[0],mode_mhz=a.mode_mhz)
            endpoints = [samples[coarse[0]]['settling'][c]['mhz'] for c in [8,247]]
            report['coverage_passed'] = min(endpoints) <= a.mode_mhz <= max(endpoints)
            failed |= not report['convergence_passed'] or not report['coverage_passed']
        elif a.stage == 'screen':
            report['candidate_bands'] = {str(mode): [c for c in coarse
                if 8 in samples[c]['baseline'] and 247 in samples[c]['baseline']
                and min(samples[c]['baseline'][k]['mhz'] for k in [8,247]) <= mode
                <= max(samples[c]['baseline'][k]['mhz'] for k in [8,247])]
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
