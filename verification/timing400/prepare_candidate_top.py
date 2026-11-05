#!/usr/bin/env python3
"""Link current candidates for structural integration, without selecting a release.

Digital power is implicit in route.v and must be connected in physical assembly.
No intermacro routing, analog behavior or physical qualification is established.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess

from check_compact_clock_tree import verify
from check_compact_mapping import LEF, LIB, YOSYS
from run_dco_qualification import ROOT, sha, save

TOP = 'IntegerPLL_400MHz_CandidateTop'
DCO = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
PG = ('VPWR', 'VGND', 'VPB', 'VNB')


def check(module):
    ports = {k: v['bits'] for k, v in module['ports'].items()}
    cells = module['cells']
    assert set(cells) == {'digital', 'oscillator', 'detector'}
    assert cells['digital']['type'] == 'IntegerPLL_AcquiringCore'
    assert cells['oscillator']['type'] == DCO
    assert cells['detector']['type'] == 'IntegerPLL_BBPD'
    digital = cells['digital']['connections']
    assert all(bits == ports[pin] for pin, bits in digital.items())
    assert cells['oscillator']['connections'] == {
        **{p: ports[p] for p in PG}, 'RESET_N': ports['RESET_N'],
        'PLLOUT': ports['PLLOUT'], 'DCO_THERM': ports['DCO_THERM'],
        'COARSETHERMAL_CODE': ports['COARSETHERMAL_CODE']}
    assert cells['detector']['connections'] == {
        **{p: ports[p] for p in PG}, 'REF': ports['REFCLK'],
        'CLKDIVR': ports['CLKDIV_RETIMED'], 'RESET_N': ports['BBPD_RESET_N'],
        'BBPD': ports['BBPD']}
    assert len(ports['DCO_THERM']) == 255 and len(ports['COARSETHERMAL_CODE']) == 47


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    base = ROOT/'build/timing400/release_001'
    route = base/'compact_incremental_headroom_001'
    eq = base/'compact_incremental_headroom_equivalence_001'
    rr, er = verify(route/'assessment.json'), verify(eq/'assessment.json')
    assert er['all_transition_and_output_functions_equivalent']
    assert sha(route/'route.v') == er['input_sha256'][str(route/'route.v')]
    projection = json.loads((eq/'before_projection.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    native = ROOT/'build/timing450/dco_c1_fine_load_001'
    physical = json.loads((native/'physical_160.json').read_text())
    assert sha(physical['rcx']) == physical['rcx_sha256']
    assert sha(physical['gds']) == physical['gds_sha256']
    dco_lef = Path(physical['gds']).parent.parent/'lef'/f'{DCO}.lef'
    sampled = ROOT/'build/timing450/interface_characterization/bbpd_sampled'
    bbpd_lef = sampled/'runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef'
    macro_declarations = f'''(* blackbox *) module {DCO} (
      inout VPWR, VGND, VPB, VNB, input RESET_N,
      input [254:0] DCO_THERM, input [46:0] COARSETHERMAL_CODE, output PLLOUT);
    endmodule
    (* blackbox *) module IntegerPLL_BBPD (
      inout VPWR, VGND, VPB, VNB, input REF, CLKDIVR, RESET_N, output [1:0] BBPD);
    endmodule
    // Physical-only cells retain instances; power is implicit in route.v.
    (* blackbox *) module sky130_fd_sc_hs__tapvpwrvgnd_1 (); endmodule
    (* blackbox *) module sky130_fd_sc_hs__diode_2 (input DIODE); endmodule
    '''
    for width in (1, 2, 4, 8):
        macro_declarations += f'(* blackbox *) module sky130_fd_sc_hs__fill_{width} (); endmodule\n'
    used = set(re.findall(r'^\s+(sky130_fd_sc_hs__\w+)\s+\S+\s*\(',
                          (route/'route.v').read_text(), re.M))
    library = set(re.findall(r'cell\s*\(\s*"?([^\s"\)]+)', LIB.read_text()))
    assert used-library == {'sky130_fd_sc_hs__diode_2', 'sky130_fd_sc_hs__tapvpwrvgnd_1',
                            *(f'sky130_fd_sc_hs__fill_{w}' for w in (1,2,4,8))}
    dco_pins = {*PG, 'RESET_N', 'PLLOUT',
                *(f'DCO_THERM[{i}]' for i in range(255)),
                *(f'COARSETHERMAL_CODE[{i}]' for i in range(47))}
    bbpd_pins = {*PG, 'REF', 'CLKDIVR', 'RESET_N', 'BBPD[0]', 'BBPD[1]'}
    for lef, expected in ((dco_lef, dco_pins), (bbpd_lef, bbpd_pins)):
        pins = re.findall(r'^\s*PIN\s+(\S+)\s*$', lef.read_text(), re.M)
        assert len(pins) == len(set(pins)) and set(pins) == expected
    files = [Path(__file__).resolve(), Path(YOSYS), LIB, LEF, route/'route.v',
             route/'assessment.json', eq/'assessment.json', eq/'before_projection.json',
             native/'physical_160.json', Path(physical['gds']), Path(physical['rcx']),
             dco_lef, bbpd_lef, sampled/'physical_assessment.json']
    inputs = {str(p): sha(p) for p in files}
    out.mkdir(parents=True)
    declarations = [f'inout wire {p}' for p in PG]
    for name, port in projection['ports'].items():
        # Expose diagnostics; macro feedback ports reverse direction at the top.
        direction = 'output' if name in ('PLLOUT', 'BBPD') else port['direction']
        width = len(port['bits'])
        declarations.append(f'{direction} wire '+(f'[{width-1}:0] ' if width>1 else '')+name)
    ports = ', '.join('.'+p+'('+p+')' for p in projection['ports'])
    pg = ', '.join('.'+p+'('+p+')' for p in PG)
    wrapper = f'''// Provisional candidate wiring; physical assembly and qualification pending.
`default_nettype none
module {TOP} ({', '.join(declarations)});
IntegerPLL_AcquiringCore digital ({ports});
{DCO} oscillator ({pg}, .RESET_N(RESET_N), .PLLOUT(PLLOUT),
 .DCO_THERM(DCO_THERM), .COARSETHERMAL_CODE(COARSETHERMAL_CODE));
IntegerPLL_BBPD detector ({pg}, .REF(REFCLK), .CLKDIVR(CLKDIV_RETIMED),
 .RESET_N(BBPD_RESET_N), .BBPD(BBPD));
endmodule
`default_nettype wire
'''
    (out/'candidate_top.v').write_text(wrapper)
    (out/'analog_blackboxes.v').write_text(macro_declarations)
    script = f'''read_liberty -lib {LIB}
read_verilog {route}/route.v
read_verilog {out}/analog_blackboxes.v {out}/candidate_top.v
hierarchy -check -top {TOP}
check -assert
write_json {out}/linked.json
'''
    (out/'link.ys').write_text(script)
    with (out/'link.log').open('w') as log:
        subprocess.run([YOSYS, '-s', str(out/'link.ys')], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=60)
    module = json.loads((out/'linked.json').read_text())['modules'][TOP]
    check(module)
    for kind in ('wrong_detector_reset', 'reversed_fine_bits'):
        bad = copy.deepcopy(module)
        if kind == 'wrong_detector_reset':
            bad['cells']['detector']['connections']['RESET_N'] = bad['ports']['RESET_N']['bits']
        else:
            bad['cells']['oscillator']['connections']['DCO_THERM'].reverse()
        try:
            check(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('fault accepted: '+kind)
    for path, digest in inputs.items():
        assert sha(path) == digest, path
    save(out/'assessment.json', dict(input_sha256=inputs,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()},
        hierarchy_and_driver_check_passed=True, structural_connections_passed=True,
        analog_lef_scalar_pins_checked=len(dco_pins)+len(bbpd_pins),
        wrong_detector_reset_rejected=True, reversed_fine_bus_rejected=True,
        digital_power_is_implicit=True, intermacro_route_completed=False,
        physical_only_cells_preserved_as_blackboxes=True,
        assembled_lvs_passed=False, analog_behavior_qualified=False,
        physical_timing_qualified=False, release_qualified=False, adopted=False, scope=__doc__))
    print('Linked current digital/DCO/BBPD candidates; 317 macro pins and two negative controls checked.')


if __name__ == '__main__':
    main()
