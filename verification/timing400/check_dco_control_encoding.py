#!/usr/bin/env python3
"""Check frozen registered tuning outputs against the native fixture encoding.

Exercises the real seed-load path at all48x256code pairs. Uses304emitted SPICE
basis decks and the retained completed native deck, without running SPICE.
Settled encoding does not qualify control glitches, analog phase response or
assembled connectivity, and contributes zero wholePLL qualification cases.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace

from prepare_functional_matrix import FROZEN, FILES
from run_dco_qualification import ROOT, sha, save
from spice_dco_postlayout import dco_netlist, parse_subckt_ports


def controls(text):
    fine, coarse = {}, {}
    for line in text.splitlines():
        m = re.fullmatch(r'VCTRL(\d+) DCO_THERM\[(\d+)\] 0 (\{VDD\}|0)', line)
        if m:
            a, index = map(int, m.group(1, 2))
            assert a == index and index not in fine
            fine[index] = int(m[3] == '{VDD}')
        m = re.fullmatch(r'VCOARSETHERM(\d+) COARSETHERMAL_CODE\[(\d+)\] 0 (\{VDD\}|0)', line)
        if m:
            a, index = map(int, m.group(1, 2))
            assert a == index and index not in coarse
            coarse[index] = int(m[3] == '{VDD}')
    assert set(fine) == set(range(255)) and set(coarse) == set(range(47))
    return sum(v << i for i, v in fine.items()), sum(v << i for i, v in coarse.items())


def bench(parameters, trace, negative=False):
    if negative:
        parameters += ',.DCO_THERM_INVERT(0)'
    return f'''`timescale 1ns/1ps
module tuning_control_check;
localparam integer DLF_UPDATE_ON_PLLOUT=0;
reg clock=0,reset_n=1;
reg [5:0] coarse=0;
reg [9:0] seed=0;
wire divided;
wire [7:0] code;
wire [254:0] fine_pins;
wire [46:0] coarse_pins;
integer c,f,stream;
always #1.25 clock=~clock;
IntegerPLL_DigitalCore #({parameters}) dut(
 .PLLOUT(clock),.RESET_N(reset_n),.BBPD(2'b00),.BBPD_CAPTURE_EN(1'b0),
 .DLF_En(1'b0),.DLF_Clear(1'b1),.DLF_Ext_Override(1'b0),.DLF_IN_POL(1'b1),
 .DLF_Ext_Data(seed),.DLF_KI(8'd0),.DLF_KP(5'd0),
 .COARSEBINARY_CODE(coarse),.MMDCLKDIV_RATIO(8'd4),
 .CLKDIV_RETIMED(divided),.DCO_CODE(code),.DCO_THERM(fine_pins),
 .COARSETHERMAL_CODE(coarse_pins));
initial begin
 stream=$fopen("{trace}","w");
 if(!stream) $fatal(1,"trace open failed");
 $fdisplay(stream,"coarse,requested_fine,observed_fine,coarse_pins_hex,fine_pins_hex");
 #0 reset_n=0;
 #0.001;
 if(code!==0 || fine_pins!=={'255\'d0' if negative else '{255{1\'b1}}'} || coarse_pins!==0)
  $fatal(1,"control reset encoding failed");
 #9.999 reset_n=1;
 repeat(8) @(posedge divided);
 for(c=0;c<{1 if negative else 48};c=c+1) begin
  for(f=0;f<{1 if negative else 256};f=f+1) begin
   @(negedge clock);coarse=c;seed=f<<2;
   repeat(3) @(posedge divided);
   #0.001;
   if(code!==f[7:0]) $fatal(1,"seed/register alignment failed at %0d,%0d",c,f);
   $fdisplay(stream,"%0d,%0d,%0d,%h,%h",c,f,code,coarse_pins,fine_pins);
  end
 end
 $fclose(stream);
 $display("TUNING_CONTROL_CHECK_DONE");
 $finish;
end
initial begin #2000000; $fatal(1,"control test timeout"); end
endmodule
'''


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT/'build/timing450/dco_c1_fine_load_001/tt_screen_160/dco_postlayout_tt_coarse_01_code_128.spice'
    provenance = source.with_suffix('.provenance.json')
    native = json.loads(provenance.read_text())
    assert native['completed'] and sha(source) == native['netlist_sha256']
    settings = SimpleNamespace(**native['parameters'])
    assert settings.therm_invert and settings.coarse_codes == '1'
    rcx = Path(settings.rcx_netlist)
    assert sha(rcx) == native['files'][str(rcx)]
    ports = parse_subckt_ports(rcx, settings.subckt_name)
    assert len(ports) == len(set(ports))
    assert sum(p.startswith('DCO_THERM[') for p in ports) == 255
    assert sum(p.startswith('COARSETHERMAL_CODE[') for p in ports) == 47
    parent = FROZEN/'IntegerPLL_AcquiringCore.v'
    parameters = re.search(r'IntegerPLL_DigitalCore\s*#\((.*?)\)\s*core\(', parent.read_text(), re.S)[1]
    assert '.DCO_THERM_INVERT' not in parameters
    core_text = (FROZEN/'IntegerPLL_DigitalCore.v').read_text()
    assert 'parameter DCO_THERM_INVERT = 1' in core_text and 'parameter DCO_CONTROL_REGISTERED = 1' in core_text
    eq = ROOT/'build/timing400/release_001/compact_incremental_headroom_equivalence_001'
    eq_report = json.loads((eq/'assessment.json').read_text())
    assert eq_report['all_transition_and_output_functions_equivalent']
    projection = eq/'before_projection.json'
    assert sha(projection) == eq_report['artifacts'][str(projection)]
    routed_ports = json.loads(projection.read_text())['modules']['IntegerPLL_AcquiringCore']['ports']
    for name, width in [('COARSETHERMAL_CODE',47), ('DCO_THERM',255), ('DCO_CODE',8), ('COARSE_CODE',6)]:
        assert routed_ports[name]['direction'] == 'output' and len(routed_ports[name]['bits']) == width
    pins = {str(p): sha(p) for p in (Path(__file__).resolve(), ROOT/'scripts/spice_dco_postlayout.py',
            source, provenance, rcx, eq/'assessment.json', projection,
            *[FROZEN/n for n in FILES], Path('/usr/bin/iverilog'), Path('/usr/bin/vvp'))}
    basis = out/'native_fixture_basis'
    basis.mkdir()
    fine_table, coarse_table = {}, {}
    for code in range(256):
        text = dco_netlist(settings, code, 1, ports)
        (basis/f'fine{code:03d}.cir').write_text(text)
        fine_table[code], _ = controls(text)
    for coarse in range(48):
        text = dco_netlist(settings, 128, coarse, ports)
        (basis/f'coarse{coarse:02d}.cir').write_text(text)
        f, coarse_table[coarse] = controls(text)
        assert f == fine_table[128]
    assert controls(source.read_text()) == (fine_table[128], coarse_table[1])
    for code in range(256):
        assert fine_table[code] == ((1 << 255)-1)^((1 << code)-1)
    for coarse in range(48):
        assert coarse_table[coarse] == (1 << coarse)-1
    records = []
    for negative in (False, True):
        directory = out/('wrong_polarity' if negative else 'actual_candidate')
        directory.mkdir()
        trace = directory/'controls.csv'
        verilog, binary = directory/'bench.v', directory/'bench.vvp'
        verilog.write_text(bench(parameters, trace, negative))
        for command, name in [(['/usr/bin/iverilog','-g2012','-s','tuning_control_check','-o',binary,
                               *[FROZEN/n for n in FILES],verilog], 'compile.log'),
                              (['/usr/bin/vvp',binary], 'run.log')]:
            with (directory/name).open('x') as log:
                result = subprocess.run(list(map(str,command)), stdout=log, stderr=subprocess.STDOUT,
                                        timeout=max(.001,deadline-time.monotonic()))
            assert result.returncode == 0, (directory/name).read_text()[-2000:]
        assert 'TUNING_CONTROL_CHECK_DONE' in (directory/'run.log').read_text()
        with trace.open() as stream:
            rows = list(csv.DictReader(stream))
        expected_pairs = {(0,0)} if negative else {(c,f) for c in range(48) for f in range(256)}
        assert len(rows) == len(expected_pairs)
        assert {(int(r['coarse']),int(r['requested_fine'])) for r in rows} == expected_pairs
        mismatches = []
        for row in rows:
            c, f = int(row['coarse']), int(row['requested_fine'])
            assert int(row['observed_fine']) == f
            if int(row['fine_pins_hex'],16) != fine_table[f] or int(row['coarse_pins_hex'],16) != coarse_table[c]:
                mismatches.append(row)
        assert bool(mismatches) == negative
        records.append(dict(negative_control=negative, code_pairs=len(rows), mismatches=mismatches,
                            actual_candidate_passed=not negative, wrong_polarity_rejected=negative))
    for path, digest in pins.items():
        assert sha(path) == digest, path
    artifacts = {str(p): sha(p) for p in out.rglob('*') if p.is_file()}
    save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, records=records,
        native_fixture_basis_decks=304, actual_registered_code_pairs_checked=12288,
        steady_encoding_matches_native_fixture=True, current_routed_port_widths_match=True,
        native_simulations_added=0, dynamic_glitch_or_phase_response_qualified=False,
        assembled_connectivity_qualified=False, calibration_model_qualified=False,
        whole_pll_qualification_cases_passed=0, release_qualified=False, scope=__doc__))
    print('Checked12288registered code pairs against304native fixture bases; wrong polarity rejected')


if __name__ == '__main__':
    main()
