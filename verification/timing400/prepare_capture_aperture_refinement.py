#!/usr/bin/env python3
"""Prepare new interior capture samples; start no native process."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from analyze_completed_capture_apertures import digest
from characterize_compact_propagation import SUPPLIES
from prepare_compact_capture_boundaries import pwl


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    analysis_path = base / 'completed_capture_aperture_analysis_001/assessment.json'
    source_path = base / 'compact_capture_boundaries_fs125_001/plan.json'
    original_deck = source_path.parent / 'batch.cir'
    shared_owner = base / 'compact_nominal_15PVT_completion_001/owner.json'
    analysis = json.loads(analysis_path.read_text())
    source = json.loads(source_path.read_text())
    deadline = json.loads(shared_owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    assert digest(source_path) == analysis['input_sha256'][str(source_path)]
    pins, aliases = {}, {}
    for name, sha in source['input_sha256'].items():
        # The old container workspace used /work/OpenPLL. Record the mapping;
        # require exact original bytes at the current canonical location.
        path = root / name.removeprefix('/work/OpenPLL/') if name.startswith('/work/OpenPLL/') else Path(name)
        assert digest(path) == sha, name
        pins[str(path)] = sha
        if str(path) != name:
            aliases[name] = str(path)
    for name, sha in analysis['input_sha256'].items():
        assert digest(name) == sha, name
        pins[name] = sha
    for path in (Path(__file__).resolve(), analysis_path, source_path, original_deck, shared_owner,
                 Path(__file__).with_name('prepare_compact_capture_boundaries.py'),
                 Path(__file__).with_name('characterize_compact_propagation.py'),
                 Path(__file__).with_name('analyze_completed_capture_apertures.py')):
        pins[str(path)] = digest(path)
    cases = []
    identities = set()
    for group in analysis['groups']:
        old_cases = [c for c in source['fixtures']
                     if (c['master'], c['kind']) == (group['master'], group['kind'])]
        for bracket in group['observed_transition_brackets']:
            template = next(c for c in old_cases if c['offset_ps'] == bracket['left_ps'])
            for offset in bracket['unsimulated_refinement_offsets_ps']:
                assert offset not in {c['offset_ps'] for c in old_cases}
                case = deepcopy(template)
                channel = 'control' if case['kind'] == 'async_release' else 'data'
                delta_ns = (offset-case['offset_ps'])/1000
                assert len(case[channel]) == 3
                case[channel] = [case[channel][0]] + [(t+delta_ns, v) for t, v in case[channel][1:]]
                case.update(offset_ps=offset, changing_input_center_ns=20+offset/1000,
                            sentinel=False, sentinel_expected_final_value=None,
                            purpose='new_interior_sample', source_bracket=bracket)
                identity = (case['master'], case['kind'], offset)
                assert identity not in identities
                identities.add(identity)
                cases.append(case)
    assert len(cases) == 54
    # Repeat separated controls to validate this batch, not failed boundary points.
    controls = [dict(deepcopy(c), purpose='separated_batch_control')
                for c in source['fixtures'] if c['sentinel']]
    assert len(controls) == 36
    cases.extend(controls)
    original = original_deck.read_text()
    header = original.split('VCLK_0 ', 1)[0]
    assert header.endswith('VSUP VDD 0 1.8\n')
    lines, columns = header.rstrip().splitlines(), []
    for index, case in enumerate(cases):
        assert case['full_clock_ramp_ps'] == case['full_changing_input_ramp_ps'] == 200
        assert case['external_load_pf'] == .005
        for channel in ('clock', 'data', 'control'):
            assert all(a[0] < b[0] for a, b in zip(case[channel], case[channel][1:]))
        aliases_for_case = {**SUPPLIES, 'CLK': f'CLK_{index}', 'D': f'D_{index}',
                            'Q': f'Q_{index}', case['control_pin']: f'R_{index}'}
        for channel, key in [('CLK', 'clock'), ('D', 'data'), ('R', 'control')]:
            lines.append(f'V{channel}_{index} {channel}_{index} 0 '+pwl(case[key]))
        lines.extend([f'XDUT_{index} '+' '.join(aliases_for_case[p] for p in case['ports'])+' '+case['master'],
                      f'CLOAD_{index} Q_{index} 0 5f'])
        columns.extend(f'V({name}_{index})' for name in ('CLK', 'D', 'R', 'Q'))
    lines.extend(['.tran 2p 28n 0 2p', '.print tran '+' '.join(columns), '.end'])
    out = base / 'capture_aperture_refinement_fs125_001'
    out.mkdir(exist_ok=False)
    deck = out / 'batch.cir'
    deck.write_text('\n'.join(lines)+'\n')
    pins[str(deck)] = digest(deck)
    for path, sha in pins.items():
        assert digest(path) == sha, path
    plan = dict(input_sha256=pins, historical_workspace_aliases=aliases,
        prepared_utc=datetime.now(timezone.utc).isoformat(), fixtures=cases, waveform_columns=columns,
        pvt=source['pvt'], stop_ns=28, max_step_ps=2, new_interior_samples=54,
        repeated_separated_batch_controls=36, shared_deadline_uptime=deadline,
        inherited_campaign_owner=str(shared_owner), budget_restarted=False,
        native_execution_started=False, automatic_identical_retry=False,
        setup_hold_recovery_removal_qualified=False, physical_timing_qualified=False,
        release_qualified=False, adopted=False,
        scope='Interior samples for the observed FS125 capture transitions only; '
              'no conservative constraints, delay-degradation limit or metastability qualification.')
    (out / 'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps(dict(output=str(out), new_samples=54, batch_controls=36, native_started=False)))


if __name__ == '__main__':
    main()
