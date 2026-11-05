"""Review measured endpoint brackets without promoting sparse probes to tuning qualification."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify


def bracket(low, high, target):
    values = [*low, *high, target]
    if not all(math.isfinite(x) and x > 0 for x in values):
        raise ValueError('positive finite frequencies required')
    if low[0] > low[1] or high[0] > high[1]:
        raise ValueError('ordered observed frequency intervals required')
    # Both endpoints must remain on their respective sides throughout the
    # measured cycles. This does not bound interpolation or model uncertainty.
    lower, upper = sorted((low, high), key=lambda x: x[0])
    return dict(observed_endpoint_bracket=lower[1] < target < upper[0],
                lower_headroom_hz=target-lower[1],
                upper_headroom_hz=upper[0]-target,
                fine_frequency_increases=high[0] > low[1])


def run(pilots, output, target=400e6):
    pins = {str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    groups = {}
    candidate = None
    for pilot in pilots:
        receipt = pilot/'assessment.json'
        manifest = pilot/'input_manifest.json'
        review = pilot/'all_cycle_assessment/assessment.json'
        metrics = pilot/'all_cycle_assessment/all_cycle_metrics.json'
        a, m, r, data = [json.loads(p.read_text()) for p in (receipt, manifest, review, metrics)]
        for record in (a, r):
            verify(record['input_sha256'])
            verify(record.get('artifacts', {}))
        if not a.get('native_worker_completed') or not r.get('all_captured_measurement_cycles_assessed'):
            raise ValueError('completed native waveform review required')
        identities = {p: h for p, h in a['input_sha256'].items() if p.endswith('/assessment.json') and 'candidate_' in Path(p).parent.name}
        if len(identities) != 1:
            raise ValueError('one physical candidate identity required')
        if candidate is None:
            candidate = identities
        elif identities != candidate:
            raise ValueError('cannot combine different physical candidates')
        for name in ('corner', 'coarse_code', 'fine_code'):
            if data[name] != a[name] or data[name] != m[name]:
                raise ValueError('native operating point mismatch')
        command = m['command']
        netlist = command[command.index('--rcx-netlist')+1]
        if a['input_sha256'].get(netlist) != sha(Path(netlist)):
            raise ValueError('pinned RC model required')
        key = (data['corner'], data['coarse_code'], netlist)
        code = data['fine_code']
        if code not in (8, 247):
            raise ValueError('declared prototype endpoint codes required')
        if code in groups.setdefault(key, {}):
            raise ValueError('duplicate endpoint')
        groups[key][code] = data['observed_frequency_interval_hz']
        for path in (receipt, manifest, review, metrics):
            digest = sha(path)
            if str(path) in pins and pins[str(path)] != digest:
                raise ValueError('conflicting evidence digest')
            pins[str(path)] = digest
    results = []
    for (corner, coarse, model), endpoints in sorted(groups.items()):
        complete = set(endpoints) == {8, 247}
        results.append(dict(corner=corner, coarse_code=coarse, model=model,
                            both_endpoints_measured=complete,
                            observed_endpoint_intervals_hz=endpoints,
                            **(bracket(endpoints[8], endpoints[247], target) if complete else {})))
    if not results:
        raise ValueError('native evidence required')
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    report = output/'bands.json'
    save(report, results)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(report): sha(report)},
         candidate_identity=candidate, target_hz=target,
         observed_bracketing_corners=sorted({r['corner'] for r in results if r.get('observed_endpoint_bracket')}),
         numerical_and_model_uncertainty_bounded=False, interior_monotonicity_qualified=False,
         final_parent_loading_included=False, analog_tuning_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run([v.resolve() for v in a.pilot], a.output.resolve())
