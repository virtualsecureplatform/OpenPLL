#!/usr/bin/env python3
"""Prepare sparse data-capture and asynchronous-release boundary observations.

No native job starts. These fixtures locate behavior needing refinement; a
sparse scan is not a setup/hold/recovery/removal table or a qualified envelope.
All transition times in the fixture descriptions are 50% crossing times.
"""
import argparse
import itertools
import json
from pathlib import Path

from characterize_compact_propagation import ROOT, PDK, SUPPLIES, XYCE
from run_dco_qualification import REQUIREMENTS, sha, save


OFFSETS_PS = (-1000, -500, -200, -100, -50, 0, 50, 100, 200, 500, 1000)


def transition(center_ns, before, after, ramp_ns=.2):
    return [(center_ns-ramp_ns/2, before*1.8),
            (center_ns+ramp_ns/2, after*1.8)]


def stimuli(kind, offset_ps, reset_value):
    assert kind in ('data_rise', 'data_fall', 'async_release')
    assert offset_ps in OFFSETS_PS and reset_value in (0, 1)
    # Two isolated edges: the first loads a known old state; the second tests
    # the changing input. The following falling edge closes the pulse.
    clock = [(0, 0)]
    for t in (10, 20):
        clock += transition(t, 0, 1)+transition(t+2, 1, 0)
    center = 20+offset_ps/1000
    if kind == 'async_release':
        data = [(0, (1-reset_value)*1.8)]
        control = [(0, 0)]+transition(center, 0, 1)
        old, new = reset_value, 1-reset_value
    else:
        new = int(kind == 'data_rise')
        old = 1-new
        data = [(0, old*1.8)]+transition(center, old, new)
        control = [(0, 0)]+transition(2, 0, 1)
    for points in (clock, data, control):
        assert all(a[0] < b[0] for a, b in zip(points, points[1:]))
    # Only separated +/-1ns controls have an asserted expected capture. Near
    # the boundary, either state or delayed/ambiguous behavior is retained.
    sentinel = offset_ps in (-1000, 1000)
    expected = (new if offset_ps < 0 else old) if sentinel else None
    return dict(clock=clock, data=data, control=control, pretest_value=old,
                changed_value=new, sentinel=sentinel,
                sentinel_expected_final_value=expected)


def pwl(points):
    return 'PWL('+' '.join(f'{t:.12g}n {v:.12g}' for t, v in points)+')'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corner', required=True, choices=['tt', 'ff', 'ss', 'sf', 'fs'])
    parser.add_argument('--temperature-c', required=True, type=int, choices=[-40, 27, 125])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    index_path = ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index = json.loads(index_path.read_text())['models']
    source_plan = ROOT/'build/timing400/release_001/compact_sequential_propagation_fs125_001/plan.json'
    source = json.loads(source_plan.read_text())
    pins = {str(p): sha(p) for p in (Path(__file__).resolve(), REQUIREMENTS, index_path, source_plan, XYCE)}
    assert json.loads(REQUIREMENTS.read_text())['voltages'] == [1.8]
    # Reuse verified PDK text and FF-function metadata, never its old stimulus.
    for name, digest in source['input_sha256'].items():
        if str(PDK) in name:
            assert sha(name) == digest, name
            pins[name] = digest
    definitions = {}
    for c in source['fixtures']:
        identity = (c['master'], c['control_pin'], c['reset_value'], tuple(c['ports']))
        assert c['master'] not in definitions or definitions[c['master']] == identity
        definitions[c['master']] = identity
    assert len(definitions) == 6
    cases, models = [], []
    for master, control, reset_value, ports in sorted(definitions.values()):
        model = Path(index[master]['model'])
        assert sha(model) == index[master]['model_sha256']
        assert set(ports) == set(SUPPLIES)|{'CLK', 'D', 'Q', control}
        pins[str(model)] = sha(model)
        models.append(model)
        for kind, offset in itertools.product(('data_rise', 'data_fall', 'async_release'), OFFSETS_PS):
            cases.append(dict(master=master, control_pin=control, reset_value=reset_value,
                ports=list(ports), kind=kind, offset_ps=offset, clock_center_ns=20,
                changing_input_center_ns=20+offset/1000,
                full_clock_ramp_ps=200, full_changing_input_ramp_ps=200,
                external_load_pf=.005, **stimuli(kind, offset, reset_value)))
    assert len(cases) == 198 and sum(c['sentinel'] for c in cases) == 36
    lines = ['* Sparse capture/release boundary scan; not qualified constraints.',
        f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {args.corner}',
        *[f'.include "{p}"' for p in models], f'.options device temp={args.temperature_c}',
        '.options timeint reltol=1e-5 abstol=1e-10', 'VSUP VDD 0 1.8']
    columns = []
    for i, case in enumerate(cases):
        aliases = {**SUPPLIES, 'CLK': f'CLK_{i}', 'D': f'D_{i}', 'Q': f'Q_{i}', case['control_pin']: f'R_{i}'}
        for channel, points in (('CLK', case['clock']), ('D', case['data']), ('R', case['control'])):
            lines.append(f'V{channel}_{i} {channel}_{i} 0 '+pwl(points))
        lines += [f'XDUT_{i} '+' '.join(aliases[p] for p in case['ports'])+' '+case['master'],
                  f'CLOAD_{i} Q_{i} 0 5f']
        columns.extend(f'V({name}_{i})' for name in ('CLK', 'D', 'R', 'Q'))
    lines += ['.tran 2p 28n 0 2p', '.print tran '+' '.join(columns), '.end']
    for path, digest in pins.items():
        assert sha(path) == digest, path
    out.mkdir(parents=True, exist_ok=False)
    deck = out/'batch.cir'
    deck.write_text('\n'.join(lines)+'\n')
    pins[str(deck)] = sha(deck)
    save(out/'plan.json', dict(input_sha256=pins, fixtures=cases, waveform_columns=columns,
        pvt=dict(corner=args.corner, temperature_c=args.temperature_c, supply_v=1.8),
        stop_ns=28, max_step_ps=2, offsets_ps=OFFSETS_PS,
        native_execution_started=False, automatic_identical_retry=False,
        total_check_budget_s=43200, setup_hold_recovery_removal_qualified=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print('Prepared198 boundary fixtures, including36 separated controls; no native job launched')


if __name__ == '__main__':
    main()
