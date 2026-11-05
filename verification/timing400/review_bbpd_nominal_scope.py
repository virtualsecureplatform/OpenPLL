#!/usr/bin/env python3
"""Review retained nominal detector observations without promoting their scope.

Rechecks retained summary/point receipts, not their raw native waveforms.
Old fixed-rail/lumped-load receiver evidence is not a new compact-route bound.
"""
import argparse
import itertools
import json
from pathlib import Path

from run_dco_qualification import ROOT, REQUIREMENTS, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    base = ROOT/'build/timing450/interface_characterization'
    phase_path = base/'bbpd_sampled/phase_transfer_final.json'
    assert sha(phase_path) == '9b3c5d75fa285b0e7b719bd30e4fa5fe0530a5909420c3e75414c2ffae8ec00e'
    phase = json.loads(phase_path.read_text())
    coupled_path = base/'coupled_receiver_sampled_pvt200ps/assessment.json'
    manifest_path = coupled_path.parent/'input_manifest.json'
    coupled = json.loads(coupled_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) == coupled['input_manifest_sha256']
    spec = json.loads(REQUIREMENTS.read_text())
    pins = {str(p): sha(p) for p in (Path(__file__).resolve(), REQUIREMENTS, phase_path, coupled_path, manifest_path)}
    curves = [c for c in phase['curves'] if c['supply_v'] == 1.8]
    expected = set(itertools.product(spec['corners'], spec['temperatures_c'], (20, 200)))
    assert {(c['corner'], c['temperature_c'], c['edge_ps']) for c in curves} == expected
    assert len(curves) == 30 and all(c['complete'] and c['monotone'] and c['exclusive_two_pulses_at_every_phase'] for c in curves)
    isolated = [dict(corner=c['corner'], temperature_c=c['temperature_c'], edge_ps=c['edge_ps'],
                    transition_bracket_ps=c['transition_bracket_ps']) for c in curves]
    nominal = []
    for name, digest in coupled['receipts'].items():
        if '_1.8V_' not in name:
            continue
        path = ROOT/Path(name).relative_to('/work/OpenPLL')
        assert sha(path) == digest, path
        pins[str(path)] = digest
        r = json.loads(path.read_text())
        assert r['supply_v'] == 1.8 and r['exit_code'] == 0 and r['simulation_completed']
        assert r['direction_and_two_event_capture_pass'] and not r['release_qualified']
        nominal.append(dict(corner=r['corner'], temperature_c=r['temperature_c'],
                            phase_ps=r['phase_ps'], edge_ps=r['edge_ps'], receipt=str(path)))
    expected = set(itertools.product(spec['corners'], spec['temperatures_c'], (-200, 200), (20, 200)))
    assert {(r['corner'], r['temperature_c'], r['phase_ps'], r['edge_ps']) for r in nominal} == expected
    assert len(nominal) == 60
    maximum_bias = max(abs(v) for c in curves for v in c['transition_bracket_ps'])
    phase_mean_limit = 1000/spec['modes_mhz'][-1]*spec['phase_mean_output_periods']*1000
    diagnostics = []
    for label in ('n100ps', 'p100ps'):
        folder = ROOT/f'build/timing400/release_001/frozen_static_bias_{label}_001'
        source = folder/'assessment.json'
        pins[str(source)] = sha(source)
        r = json.loads(source.read_text())
        assert r['qualification_cases_passed'] == 0 and not r['interface_model_qualified']
        for mode in spec['modes_mhz']:
            path = folder/f'{mode}MHz/trace_acceptance.json'
            pins[str(path)] = sha(path)
            observed = json.loads(path.read_text())
            assert observed['passed'] and not observed['whole_pll_qualification_pass']
            diagnostics.append(dict(static_threshold_ps=r['static_detector_threshold_ps'],
                mode_mhz=mode, trace_acceptance=str(path), trace_passed=True))
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, isolated_nominal_curves=isolated,
        coupled_nominal_point_receipts=nominal, static_bias_diagnostics=diagnostics,
        maximum_reported_isolated_transition_endpoint_ps=maximum_bias,
        reported_isolated_transition_bracket_widths_ps=sorted({c['transition_bracket_ps'][1]-c['transition_bracket_ps'][0] for c in curves}),
        phase_mean_limit_at400mhz_ps=phase_mean_limit,
        isolated_static_bias_alone_exceeds_mean_limit=maximum_bias > phase_mean_limit,
        raw_prior_native_waveforms_reaudited_here=False,
        original_receiver_extraction_limitations=manifest['receiver_extraction_limitations'],
        required_before_physical_reuse=[
            'Match the exact detector macro and port/reset convention.',
            'Enclose the current receiver topology, extracted RC, pin loads, clock/reset conditions and rail/noise assumptions.',
            'Validate near-coincident capture/aperture and metastability assumptions with independent holdouts.',
            'Run the physical-model wholePLL matrix and directed changes against unchanged phase/frequency requirements.'],
        current_compact_interface_bounds_qualified=False, release_gains_selected=False,
        qualified_whole_pll_cases=0, physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print('Reviewed30 nominal isolated curves,60 coupled receipts and8 static-bias diagnostics; no scope promotion')


if __name__ == '__main__':
    main()
