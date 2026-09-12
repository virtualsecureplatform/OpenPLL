#!/usr/bin/env python3
"""Independent engineering acceptance and content-addressed run provenance."""
import hashlib
import json
from pathlib import Path

import numpy as np

SPEC_PATH = Path(__file__).resolve().parents[1] / 'verification/engineering.json'


def load_spec(path=SPEC_PATH):
    return json.loads(Path(path).read_text())


def fingerprint(paths, parameters):
    """Hash all supplied source/model files, including directory contents.

    Callers must supply the complete PDK/model directory, not just its top-level
    include. Cache validity is tied to content, not timestamps or a passing log.
    """
    files = {}
    for item in paths:
        p = Path(item).resolve(strict=True)
        for f in sorted(p.rglob('*')) if p.is_dir() else [p]:
            if f.is_file():
                files[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    record = dict(files=files, parameters=parameters)
    record['fingerprint'] = hashlib.sha256(
        json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return record


def evaluate_trace(events, target_mhz, enabled_ns, spec=None):
    """Evaluate measured edge times; malformed/incomplete data cannot pass.

    Acquisition is relative to enabled_ns (the stimulus event), not the RTL
    TRACKING flag. Missing divided-clock cycles are detected independently of
    wrapped phase, which otherwise hides an exact reference-period slip.
    """
    spec = spec or load_spec()
    if target_mhz not in spec['modes_mhz']:
        raise ValueError('unsupported output mode')
    arrays = [np.asarray(events[k], dtype=float) for k in ('REF', 'DIV', 'OUT')]
    for a in arrays:
        if a.ndim != 2 or a.shape[1] < 2 or len(a) < 3:
            raise ValueError('insufficient edge data')
        if not np.isfinite(a).all() or not np.all(np.diff(a[:, 0]) > 0):
            raise ValueError('non-finite or non-monotonic trace')
    ref, div, osc = arrays
    tref = 1000 / spec['reference_mhz']
    tout = 1000 / target_mhz
    width = spec['window_ns']
    # Follow the actual reference edges, including a deliberate reference-phase
    # disturbance. Using only the first reference edge would reject a loop that
    # correctly relocks to the new phase. Windows exclude extrapolated endpoints.
    ref_cycles = np.interp(div[:, 0], ref[:, 0], np.arange(len(ref)))
    raw = ((ref_cycles + .5) % 1 - .5) * tref
    unwrapped = np.unwrap(raw * 2 * np.pi / tref) * tref / (2 * np.pi)
    end = min(a[-1, 0] for a in arrays)
    start = max(enabled_ns, *(a[0, 0] for a in arrays))
    windows = []
    for right in np.arange(end, start + width, -width)[::-1]:
        left = right - width
        dmask = (div[:, 0] >= left) & (div[:, 0] <= right)
        omask = (osc[:, 0] >= left) & (osc[:, 0] <= right)
        d, o, ph = div[dmask], osc[omask], unwrapped[dmask]
        if len(d) < 3 or len(o) < 3:
            windows.append(dict(start_ns=float(left), end_ns=float(right), passed=False,
                                failure='insufficient_edges'))
            continue
        freq = 1000 * (len(o) - 1) / (o[-1, 0] - o[0, 0])
        error = abs(freq / target_mhz - 1) * 1e6
        span = float(np.ptp(ph))
        drift = float(np.polyfit(d[:, 0] - d[0, 0], ph, 1)[0] * (d[-1, 0] - d[0, 0]))
        mean = float((ph.mean() + tref / 2) % tref - tref / 2)
        # Include the preceding edge to detect a slip across a window boundary.
        indices = np.flatnonzero(dmask)
        periods = np.diff(div[max(0, indices[0]-1):indices[-1]+1, 0])
        out_indices = np.flatnonzero(omask)
        out_periods = np.diff(osc[max(0,out_indices[0]-1):out_indices[-1]+1,0])
        slip = bool(np.any((periods < .5*tref) | (periods > 1.5*tref)) or
                    np.any((out_periods < .5*tout) | (out_periods > 1.5*tout)))
        rail = bool(np.any((d[:, 1] <= 0) | (d[:, 1] >= 255)) or
                    np.any((o[:, 1] <= 0) | (o[:, 1] >= 255)))
        passed = (error <= spec['frequency_error_ppm'] and
                  span <= tout * spec['phase_span_output_periods'] and
                  abs(mean) <= tout * spec['phase_mean_output_periods'] and
                  abs(drift) <= tout * spec['phase_drift_output_periods'] and
                  not slip and not rail)
        windows.append(dict(start_ns=float(left), end_ns=float(right), frequency_mhz=float(freq),
                            frequency_error_ppm=float(error), phase_span_ns=span,
                            phase_mean_ns=mean, phase_drift_ns=drift,
                            cycle_slip=slip, rail=rail, passed=bool(passed)))
    count = spec['sustained_windows']
    final_pass = len(windows) >= count and all(w['passed'] for w in windows[-count:])
    last_bad = max((i for i, w in enumerate(windows) if not w['passed']), default=-1)
    first = last_bad + 1
    acquired = windows[first + count - 1]['end_ns'] if len(windows)-first >= count else None
    within_deadline = acquired is not None and acquired-enabled_ns <= spec['acquisition_limit_ns']
    return dict(target_mhz=target_mhz, stimulus_ns=enabled_ns, windows=windows,
                sustained_final_pass=final_pass, acquisition_confirmed_ns=acquired,
                passed=bool(final_pass and within_deadline), evidence='trace_functional_only')
