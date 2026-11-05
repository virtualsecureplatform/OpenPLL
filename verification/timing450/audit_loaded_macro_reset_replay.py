#!/usr/bin/env python3
"""Audit one native loaded-event committed-bundle physical macro-reset waveform and its actual signed-event RTL replay.

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
    assert '.tran 5p 350n 0 5p' in deck
    assert '187.05n {VDD} 187.07n 0 188.55n 0 188.57n {VDD}' in deck
    text = (native_dir/'loaded.prn').read_text()
    header = ['Index','TIME']+['V('+n+')' for n in ('REF','CLKDIVR','BBPD[0]','BBPD[1]','UPQ','DNQ','UP1','UP2','DN1','DN2','CLKUP1','DATAUP1','CLKDN1','DATADN1','READY1','READY2','EVENT_RESET','PIPE_RESET','TRACK_ACTIVE','COMMAND_RUN','BBPD_RESET_PHY')]
    assert text.splitlines()[0].split()==header
    rows = [list(map(float,line.split())) for line in text.splitlines()
            if line.split() and line.split()[0].isdigit()]
    assert rows and all(len(row)==23 and all(map(math.isfinite,row)) for row in rows)
    assert rows[0][1]==0 and rows[-1][1]>=350e-9-1e-14
    assert 'End of Xyce(TM) Simulation' in text
    assert all(a[1]<b[1] for a,b in zip(rows,rows[1:]))
    event_rise, event_fall = crossings(rows,18,supply/2)
    command_rise, command_fall = crossings(rows,21,supply/2)
    assert len(command_rise)==len(command_fall)==1
    assert abs(command_rise[0]-command_fall[0]-1.5)<1e-7
    withdraw_falls = [t for t in event_fall if command_fall[0]<=t<command_rise[0]+20]
    assert len(withdraw_falls)==1
    reset_assert = withdraw_falls[0]
    ref_rises, _ = crossings(rows,2,supply/2)
    macro_rises, macro_falls = crossings(rows,22,supply/2)
    macro_assertions = [t for t in macro_falls if command_fall[0]<=t<command_rise[0]+20]
    macro_releases = [t for t in macro_rises if t>command_rise[0]]
    assert len(macro_assertions)==len(macro_releases)==1
    next_ref = next(t for t in ref_rises if t>macro_releases[0])
    window_stop=next_ref+35
    assert window_stop<350
    assert abs(replay['consumption_window_ns'][0]-next_ref)<1e-8
    assert abs(replay['consumption_window_ns'][1]-window_stop)<1e-8
    # The detector cannot sample a fresh REF event until its physical reset releases.
    assert macro_assertions[0]<macro_releases[0]<next_ref
    assert len([t for t in macro_rises if t<command_fall[0]])>=1
    log = (replay_dir/'run.log').read_text()
    events = [(direction,float(t)) for direction,t in
              re.findall(r'accepted_(UP|DN) time_ns=([0-9.]+)',log)]
    assert 'receiver_ready_replay=pass' in log
    assert events==sorted(events,key=lambda e:e[1]) and all(0<=t<=350 for _,t in events)
    counts = re.search(r'receiver_pvt_replay up=(\d+) dn=(\d+) post_up=(\d+) post_dn=(\d+)',log)
    assert counts
    observed = tuple(map(int,counts.groups()))
    measured = tuple(sum(direction==name and (not post or next_ref<=t<=window_stop)
                         for direction,t in events) for post,name in
                     [(False,'UP'),(False,'DN'),(True,'UP'),(True,'DN')])
    assert observed==measured
    stale = [(direction,t) for direction,t in events if reset_assert<=t<next_ref]
    fresh = [(direction,t) for direction,t in events if next_ref<=t<=window_stop]
    opposite = [(direction,t) for direction,t in events if direction!=expected]
    pre = [(direction,t) for direction,t in events if t<command_fall[0]]
    expected_column = 9 if phase>0 else 11
    pre_sample = next(row for row in reversed(rows) if row[1]*1e9<command_fall[0])
    loaded_before_withdrawal = pre_sample[expected_column]>=supply/2
    passed = (not stale and len(fresh)==1 and fresh[0][0]==expected and not opposite
              and len(pre)==1 and pre[0][0]==expected and loaded_before_withdrawal)
    verify(pins)
    result = {'pass':passed,'supply_v':supply,'phase_ps':phase,'expected_direction':expected,
              'event_reset_assert_ns':reset_assert,'next_ref_opportunity_ns':next_ref, 'macro_reset_assert_ns':macro_assertions[0], 'macro_reset_release_ns':macro_releases[0], 'consumption_window_ns':[next_ref,window_stop],
              'pre_withdrawal_consumed_events':pre,'physical_storage_loaded_before_withdrawal':loaded_before_withdrawal,'consumed_events':events,'stale_events_after_reset_before_next_ref':stale,
              'fresh_events':fresh,'opposite_events':opposite,'sha256':pins,
              'release_qualified':False,'selected':False,
              'limitations':['One deterministic transient with half-supply storage/reset thresholds',
                             'Measured storage/reset replaces RTL state; remaining logic uses RTL timing',
                             'Fixed nominal cellRC/max routeRC/ideal committed fast/fine RUN/coarse/divided-clock controls; no MTBF or fullPLL proof']}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'}))
    if not passed:
        raise RuntimeError('Stale, missing or wrong-direction event consumption')


if __name__ == '__main__':
    main()
