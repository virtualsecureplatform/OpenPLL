#!/usr/bin/env python3
"""Replay a terminal loaded-reset trace at any required mode, with clocks through its full duration.

This supports both signed phase directions and all three supply thresholds.
It bypasses only measured receiver storage. It is a deterministic mixed-boundary
functional check, not gate timing, analog threshold sensitivity or MTBF signoff.
"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from characterize_bbpd import sha, verify, crossings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--swap-direction-control', action='store_true',
                        help='Swap measured UP/DN storage; expected direction must reject this control')
    parser.add_argument("--mode-mhz", type=int, choices=(100,250,300,400,450), required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    deck = (directory / 'loaded.cir').read_text()
    clock_match = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([0-9.]+)n ([0-9.]+)n\)$', deck, re.M)
    assert clock_match
    plateau_ns, period_ns = map(float, clock_match.groups())
    assert abs(period_ns*args.mode_mhz-1000) < 3e-7
    assert abs(plateau_ns+.2-period_ns/2) < 1e-9
    duration_ns = 350 if args.mode_mhz == 450 else 450
    assert f'.tran 5p {duration_ns}n 0 5p' in deck
    duration_s = duration_ns*1e-9
    duration_fs = round(duration_ns*1e6)
    receipt = directory / 'assessment.json'
    assessment = json.loads(receipt.read_text())
    assert assessment['simulation_completed'] and assessment['exit_code'] == 0
    verify(assessment['sha256'])
    manifest = directory / 'input_manifest.json'
    if not manifest.exists():
        manifest = directory.parent / 'input_manifest.json'
    if 'input_manifest_sha256' in assessment:
        assert sha(manifest) == assessment['input_manifest_sha256']
    pins = json.loads(manifest.read_text())['sha256']
    verify(pins)
    pins.update({str(receipt): sha(receipt), str(manifest): sha(manifest),
                 str(Path(__file__).resolve()): sha(Path(__file__).resolve())})
    wave = directory / 'loaded.prn'
    text = wave.read_text()
    expected_header = ['Index', 'TIME'] + ['V('+n+')' for n in ('REF','CLKDIVR','BBPD[0]','BBPD[1]','UPQ','DNQ','UP1','UP2','DN1','DN2','CLKUP1','DATAUP1','CLKDN1','DATADN1','READY1','READY2','EVENT_RESET','PIPE_RESET','TRACK_ACTIVE','COMMAND_RUN','BBPD_RESET_PHY')]
    assert text.splitlines()[0].split() == expected_header
    rows = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            row = list(map(float, fields))
            assert len(row) == 23 and all(map(math.isfinite, row))
            rows.append(row)
    assert rows[0][1] == 0 and rows[-1][1] >= duration_s - 1e-14
    assert 'End of Xyce(TM) Simulation' in text
    assert all(b[1] > a[1] for a, b in zip(rows, rows[1:]))
    deck = (directory / 'loaded.cir').read_text()
    supply = float(re.search(r'(?m)^\.param VDD=([0-9.]+)$', deck)[1])
    assert supply in (1.62, 1.8, 1.95)
    div_delay = float(re.search(r'(?m)^VDIV CLKDIVR 0 PULSE\(0 \{VDD\} ([0-9.]+)n ', deck)[1])
    phase = round((div_delay - 10) * 1000)
    assert phase in (-250, 250)
    expected_up = 1 if phase > 0 else 0
    expected_dn = 1 - expected_up
    # Require actual macro-reset release after withdrawal; derive the next
    # detector sampling opportunity from the independently simulated REF trace.
    macro_rises, macro_falls = crossings(rows, 22, supply/2, start=0, stop=duration_s)
    command_rises, command_falls = crossings(rows, 21, supply/2, start=0, stop=duration_s)
    assert len(command_falls)==len(command_rises)==1
    assert abs((command_rises[0]-command_falls[0])*1e9-1.5)<1e-7
    releases = [t for t in macro_rises if t > command_rises[0]]
    assert len(releases)==1
    ref_rises, _ = crossings(rows, 2, supply/2, start=0, stop=duration_s)
    window_start_ns = next(t for t in ref_rises if t>releases[0])*1e9
    window_stop_ns = window_start_ns+35*450/args.mode_mhz
    assert window_stop_ns < duration_ns
    events = []
    for name, column in (('up1', 8), ('up2', 9), ('dn1', 10), ('dn2', 11),
                         ('ready1', 16), ('ready2', 17), ('capture', 20), ('physical_reset', 19)):
        assert rows[0][column] < .2 * supply
        rising, falling = crossings(rows, column, supply / 2, start=0, stop=duration_s)
        events.extend((round(t * 1e15), name, value)
                      for value, times in ((1, rising), (0, falling)) for t in times)
    # Reproduce every source threshold edge through the full native trace.
    assert '187.05n {VDD} 187.07n 0 188.55n 0 188.57n {VDD}' in deck
    for cycle in range(math.ceil(duration_ns/period_ns)+1):
        for offset, value in ((.1, 1), (plateau_ns+.3, 0)):
            time_fs = round((cycle*period_ns+offset)*1e6)
            if time_fs < duration_fs:
                events.append((time_fs, 'pll', value))
    pll_edge_count = sum(name == 'pll' for _, name, _ in events)
    assert pll_edge_count >= math.floor(2*duration_ns/period_ns)-1
    events.extend([(1000, 'reset_n', 0), (1_020_000, 'reset_n', 1)])
    events.sort()
    statements = []
    previous = 0
    for time_fs, name, value in events:
        assert time_fs >= previous
        statements.append(f'#{(time_fs-previous)/1e6:.6f} {name}=1\'b{value};')
        previous = time_fs
    statements.append(f'#{(duration_fs-previous)/1e6:.6f};')
    testbench = r'''`timescale 1ns/1fs
module replay;
reg pll=0,reset_n=1,capture=0,physical_reset=0;
reg up1=0,up2=0,dn1=0,dn2=0,ready1=0,ready2=0;
wire [1:0] physical_up={up2,up1},physical_dn={dn2,dn1},physical_ready={ready2,ready1};
integer accepted_up=0,accepted_dn=0,post_up=0,post_dn=0;
IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),
 .MMD_REGISTER_CONFIG(1),.MMD_RATIO_WIDTH(5),.MMD_COUNTDOWN(1),.MMD_CONFIG_PIPELINE(1),
 .SYNCHRONIZE_RESETS(1),.BBPD_EVENT_CDC(1),.BBPD_CAPTURE_INDEPENDENT(1),
 .REGISTER_BBPD_DECISION(1)) dut(
 .PLLOUT(pll),.RESET_N(reset_n),.BBPD(2'b00),.BBPD_CAPTURE_EN(capture),
 .DLF_En(1'b1),.DLF_Clear(1'b0),.DLF_Ext_Override(1'b0),.DLF_IN_POL(1'b1),
 .DLF_Ext_Data(10'd512),.DLF_KI(8'd4),.DLF_KP(5'd0),
 .COARSEBINARY_CODE(6'd0),.MMDCLKDIV_RATIO(8'd__RATIO__));
initial begin
 force dut.fast_reset_n=physical_reset;
 force dut.gen_event_cdc.up_pipe=physical_up;
 force dut.gen_event_cdc.dn_pipe=physical_dn;
 force dut.gen_event_cdc.capture_pipe=physical_ready;
end
always @(posedge pll) begin
 if(dut.fast_reset_n && dut.bbpd_capture_active && dut.bbpd_receive_ready && dut.bbpd_seen==0) begin
  if(dut.bbpd_up_event_new) begin
   accepted_up=accepted_up+1;
   if($realtime>=__START__ && $realtime<=__STOP__) post_up=post_up+1;
   $display("accepted_UP time_ns=%0.6f",$realtime);
  end
  if(dut.bbpd_dn_event_new) begin
   accepted_dn=accepted_dn+1;
   if($realtime>=__START__ && $realtime<=__STOP__) post_dn=post_dn+1;
   $display("accepted_DN time_ns=%0.6f",$realtime);
  end
 end
 #0.000001;
 if(dut.gen_event_cdc.up_pipe!==physical_up || dut.gen_event_cdc.dn_pipe!==physical_dn || dut.gen_event_cdc.capture_pipe!==physical_ready)
  $fatal(1,"physical stage replay does not drive RTL storage");
end
initial begin
__EVENTS__
 $display("receiver_pvt_replay up=%0d dn=%0d post_up=%0d post_dn=%0d",accepted_up,accepted_dn,post_up,post_dn);
 if(post_up!=__UP__ || post_dn!=__DN__ || __OPPOSITE__!=0)
  $fatal(1,"post-withdrawal replay loses new event or accepts wrong direction");
 $display("receiver_ready_replay=pass");$finish;
end
endmodule
'''.replace('__RATIO__', str(args.mode_mhz//25)).replace('__EVENTS__', '\n'.join(statements)).replace('__START__', f'{window_start_ns:.9f}').replace('__STOP__', f'{window_stop_ns:.9f}').replace('__UP__', str(expected_up)).replace('__DN__', str(expected_dn)).replace('__OPPOSITE__', 'accepted_dn' if expected_up else 'accepted_up')
    if args.swap_direction_control:
        testbench = testbench.replace('physical_up={up2,up1},physical_dn={dn2,dn1}',
                                     'physical_up={dn2,dn1},physical_dn={up2,up1}')
    args.output.mkdir(parents=True, exist_ok=False)
    bench = args.output / 'replay.v'
    bench.write_text(testbench)
    root = Path(__file__).resolve().parents[2]
    candidate_rtl = root / ('build/timing450/hs/closure/handoff_candidate/'
                            'build/timing450/hs/closure/iteration_026/'
                            'variant_hot_electrical/verification/timing450/rtl')
    sources = [candidate_rtl / 'IntegerPLL_DigitalCore.v',
               candidate_rtl / 'IntegerPLL_MMD_Retimer.v',
               *(root / 'rtl' / name for name in
                 ('IntegerPLL_DLF.v', 'IntegerPLL_B2TH.v', 'IntegerPLL_Divider.v'))]
    for path in [bench, *sources, Path('/usr/bin/iverilog'), Path('/usr/bin/vvp')]:
        pins[str(path.resolve())] = sha(path)
    verify(pins)
    executable = args.output / 'replay.vvp'
    with (args.output / 'compile.log').open('w') as log:
        result = subprocess.run(['/usr/bin/iverilog', '-g2012', '-s', 'replay',
                                 '-o', str(executable), str(bench), *map(str, sources)],
                                stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0
    with (args.output / 'run.log').open('w') as log:
        result = subprocess.run(['/usr/bin/vvp', str(executable)], stdout=log, stderr=subprocess.STDOUT)
    verify(pins)
    output = (args.output / 'run.log').read_text()
    passed = result.returncode == 0 and 'receiver_ready_replay=pass' in output
    control_rejected = (args.swap_direction_control and result.returncode != 0
                        and 'post-withdrawal replay loses new event or accepts wrong direction' in output)
    report = {'pass': passed, 'exit_code': result.returncode, 'sha256': pins,
              'mode_mhz': args.mode_mhz, 'simulation_time_ns': duration_ns, 'pll_edges_replayed': pll_edge_count,
              'negative_control': args.swap_direction_control, 'supply_v': supply, 'phase_ps': phase,
              'consumption_window_ns': [window_start_ns,window_stop_ns], 'macro_release_after_withdrawal_ns':releases[0]*1e9, 'expected_post_up': expected_up, 'expected_post_dn': expected_dn,
              'negative_control_rejected': control_rejected,
              'artifacts': {str(p): sha(p) for p in (executable, args.output / 'compile.log', args.output / 'run.log')},
              'release_qualified': False, 'selected': False,
              'limitations': ['Single deterministic transient and half-supply threshold; accepts legitimate pre-withdrawal events',
                              'Checks exactly one signed post-withdrawal consumption in the post-release response window (15.75 output-clock periods) and no opposite-direction consumption in the full window; does not alone establish absence of stale same-direction consumption',
                              'Measured receiver/guard storage replaces corresponding RTL registers; measured pipe reset drives fast_reset_n; measured tracking-active drives capture enable',
                              'Remaining control logic has RTL timing, not mapped gate timing',
                              'Actual mapped macro reset drives the analog detector; acquisition-inactive, committed fast/fine RUN/coarse and divided-clock cuts remain ideal; no complete acquisition, physical DCO or statistical MTBF']}
    (args.output / 'assessment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(output)
    if not (control_rejected if args.swap_direction_control else passed):
        raise RuntimeError('Mapped receiver/guard replay failed')


if __name__ == '__main__':
    main()
