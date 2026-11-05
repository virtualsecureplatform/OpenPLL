#!/usr/bin/env python3
"""Audit one native reset waveform and its actual signed-event RTL replay.

Checks no same-direction stale consumption after the measured event-reset
assertion and before the next REF opportunity, in addition to fresh consumption.
This is a deterministic mixed-boundary check, not mapped gate timing or MTBF.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(pins):
    for path, wanted in pins.items():
        if sha(path) != wanted:
            raise RuntimeError(f'Changed artifact: {path}')


def crossings(rows, column, threshold):
    rises, falls = [], []
    for a, b in zip(rows, rows[1:]):
        if a[column] < threshold <= b[column] or a[column] >= threshold > b[column]:
            t = a[1] + (threshold-a[column])*(b[1]-a[1])/(b[column]-a[column])
            (rises if b[column] > a[column] else falls).append(t*1e9)
    return rises, falls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-directory', type=Path, required=True)
    parser.add_argument('--replay-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    native_dir, replay_dir = args.native_directory.resolve(), args.replay_directory.resolve()
    native_path, replay_path = native_dir/'assessment.json', replay_dir/'assessment.json'
    native, replay = json.loads(native_path.read_text()), json.loads(replay_path.read_text())
    assert native['exit_code'] == 0 and native['simulation_completed']
    assert replay['exit_code'] == 0 and replay['pass'] and not replay['negative_control']
    pins = {**native['sha256'], **replay['sha256'], **replay['artifacts']}
    pins.update({str(p):sha(p) for p in [native_path,replay_path,Path(__file__).resolve()]})
    verify(pins)
    deck = (native_dir/'loaded.cir').read_text()
    supply = float(re.search(r'(?m)^\.param VDD=([0-9.]+)$',deck)[1])
    div_delay = float(re.search(r'(?m)^VDIV CLKDIVR 0 PULSE\(0 \{VDD\} ([0-9.]+)n ',deck)[1])
    phase = (div_delay-10)*1000
    assert abs(abs(phase)-250) < 1e-8 and supply in (1.62,1.8,1.95)
    expected = 'UP' if phase > 0 else 'DN'
    text = (native_dir/'loaded.prn').read_text()
    rows = [list(map(float,line.split())) for line in text.splitlines()
            if line.split() and line.split()[0].isdigit()]
    assert rows and all(len(row)==22 and all(map(math.isfinite,row)) for row in rows)
    assert rows[0][1]==0 and rows[-1][1]>=90e-9-1e-14
    assert 'End of Xyce(TM) Simulation' in text
    assert all(a[1]<b[1] for a,b in zip(rows,rows[1:]))
    event_rise, event_fall = crossings(rows,18,supply/2)
    command_rise, command_fall = crossings(rows,21,supply/2)
    assert len(command_rise)==len(command_fall)==1
    assert abs(command_rise[0]-command_fall[0]-1.5)<1e-7
    withdraw_falls = [t for t in event_fall if command_fall[0]<=t<45]
    assert len(withdraw_falls)==1
    reset_assert = withdraw_falls[0]
    ref_rises, _ = crossings(rows,2,supply/2)
    next_ref = next(t for t in ref_rises if t>command_rise[0])
    # A new event cannot be sampled before the actual next post-withdrawal REF.
    assert 50<=next_ref<51
    log = (replay_dir/'run.log').read_text()
    events = [(direction,float(t)) for direction,t in
              re.findall(r'accepted_(UP|DN) time_ns=([0-9.]+)',log)]
    assert 'receiver_ready_replay=pass' in log
    assert events==sorted(events,key=lambda e:e[1]) and all(0<=t<=90 for _,t in events)
    counts = re.search(r'receiver_pvt_replay up=(\d+) dn=(\d+) post_up=(\d+) post_dn=(\d+)',log)
    assert counts
    observed = tuple(map(int,counts.groups()))
    measured = tuple(sum(direction==name and (not post or 50<=t<=85)
                         for direction,t in events) for post,name in
                     [(False,'UP'),(False,'DN'),(True,'UP'),(True,'DN')])
    assert observed==measured
    stale = [(direction,t) for direction,t in events if reset_assert<=t<next_ref]
    fresh = [(direction,t) for direction,t in events if 50<=t<=85]
    opposite = [(direction,t) for direction,t in events if direction!=expected]
    passed = not stale and len(fresh)==1 and fresh[0][0]==expected and not opposite
    verify(pins)
    result = {'pass':passed,'supply_v':supply,'phase_ps':phase,'expected_direction':expected,
              'event_reset_assert_ns':reset_assert,'next_ref_opportunity_ns':next_ref,
              'consumed_events':events,'stale_events_after_reset_before_next_ref':stale,
              'fresh_events':fresh,'opposite_events':opposite,'sha256':pins,
              'release_qualified':False,'selected':False,
              'limitations':['One deterministic transient with half-supply storage/reset thresholds',
                             'Measured storage/reset replaces RTL state; remaining logic uses RTL timing',
                             'Fixed nominal cellRC/max routeRC/ideal controls; no MTBF or fullPLL proof']}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'}))
    if not passed:
        raise RuntimeError('Stale, missing or wrong-direction event consumption')


if __name__ == '__main__':
    main()
