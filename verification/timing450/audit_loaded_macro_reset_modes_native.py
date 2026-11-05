#!/usr/bin/env python3
"""Audit terminal 350ns loaded-event committed-bundle reset output and event exercise, without claiming PLL signoff."""
import argparse
import json
import math
import re
from pathlib import Path
from audit_receiver_reset_replay import crossings, sha, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument("--mode-mhz", type=int, choices=(100,250,300,400,450), required=True)
    args = parser.parse_args()
    duration_ns = 350 if args.mode_mhz == 450 else 450
    assert not args.output.exists()
    directory = args.directory.resolve()
    receipt = directory / 'assessment.json'
    native = json.loads(receipt.read_text())
    assert native['exit_code'] == 0 and native['simulation_completed']
    manifest = directory / 'input_manifest.json'
    assert sha(manifest) == native['input_manifest_sha256']
    pins = {**json.loads(manifest.read_text())['sha256'], **native['sha256']}
    for path in (receipt, manifest, Path(__file__).resolve(),
                 Path(__file__).with_name('audit_receiver_reset_replay.py').resolve()):
        pins[str(path)] = sha(path)
    verify(pins)
    text = (directory / 'loaded.prn').read_text()
    names = ('REF', 'CLKDIVR', 'BBPD[0]', 'BBPD[1]', 'UPQ', 'DNQ',
             'UP1', 'UP2', 'DN1', 'DN2', 'CLKUP1', 'DATAUP1', 'CLKDN1',
             'DATADN1', 'READY1', 'READY2', 'EVENT_RESET', 'PIPE_RESET',
             'TRACK_ACTIVE', 'COMMAND_RUN', 'BBPD_RESET_PHY')
    assert text.splitlines()[0].split() == ['Index', 'TIME'] + ['V('+n+')' for n in names]
    rows = [list(map(float, line.split())) for line in text.splitlines()
            if line.split() and line.split()[0].isdigit()]
    assert rows and all(len(row) == 23 and all(map(math.isfinite, row)) for row in rows)
    assert rows[0][1] == 0 and rows[-1][1] >= duration_ns*1e-9 - 1e-14
    assert 'End of Xyce(TM) Simulation' in text
    assert all(a[1] < b[1] for a, b in zip(rows, rows[1:]))
    deck = (directory / 'loaded.cir').read_text()
    supply = float(re.search(r'(?m)^\.param VDD=([0-9.]+)$', deck)[1])
    assert supply in (1.62,1.8,1.95)
    corner = re.search(r'^\.lib .+ (tt|ff|ss|sf|fs)$', deck, re.M)[1]
    temperature = float(re.search(r'^\.options device temp=([-0-9.]+)$', deck, re.M)[1])
    pvt = {'corner':corner, 'supply_v':supply, 'temperature_c':temperature}
    for record in (json.loads(manifest.read_text()), native):
        if 'pvt' in record:
            assert record['pvt'] == pvt
        if 'mode_mhz' in record:
            assert record['mode_mhz'] == args.mode_mhz
    assert f'.tran 5p {duration_ns}n 0 5p' in deck
    clock = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([0-9.]+)n ([0-9.]+)n\)$', deck, re.M)
    assert clock
    plateau, period = map(float, clock.groups())
    assert abs(period*args.mode_mhz-1000)<3e-7
    assert abs(plateau+.2-period/2)<1e-9
    assert 'XBBPD BBPD[0] BBPD[1] CLKDIVR REF BBPD_RESET_PHY ' in deck
    traces = {}
    for column, name in enumerate(names, 2):
        rise, fall = crossings(rows, column, supply/2)
        traces[name] = {'minimum_v': min(r[column] for r in rows),
                        'maximum_v': max(r[column] for r in rows),
                        'rising_ns': rise, 'falling_ns': fall}
    macro = traces['BBPD_RESET_PHY']
    reset_released = macro['maximum_v'] >= supply/2
    storage_exercised = any(traces[n]['rising_ns'] for n in ('UP2', 'DN2'))
    report = {'pvt':pvt,'mode_mhz':args.mode_mhz,'simulation_time_ns':duration_ns,'native_complete_wave_audit_pass': True,
              'macro_reset_released': reset_released,
              'event_storage_exercised': storage_exercised,
              'functional_qualification_pass': False,
              'classification': ('consumption_audit_required' if reset_released and storage_exercised
                                 else 'reset_or_event_not_exercised'),
              'signals': traces, 'sha256': pins,
              'release_qualified': False, 'selected': False,
              'limitations': ['One recorded PVT/mode trace; nominal cellRC and fixed routeRC',
                              'Ideal clocks/configuration/ties/acquisition-inactive/committed RUN cuts',
                              'Native completion alone cannot prove active detector or fresh/stale consumption',
                              'No complete acquisition, statistical metastability or wholePLL proof']}
    verify(pins)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('signals', 'sha256')}))


if __name__ == '__main__':
    main()
