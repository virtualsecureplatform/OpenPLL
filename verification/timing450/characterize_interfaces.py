#!/usr/bin/env python3
"""Measure routed input loads and export SDF without claiming timed simulation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from run import REPO, TOOLS, run

PORTS = ('BBPD[0]', 'BBPD[1]', 'PLLOUT')
PROBE = '''`timescale 1ns/1ps
module checked_ff(input CLK,D, output reg Q);
 reg notifier=0;
 always @(posedge CLK) Q<=D;
 specify
  $setuphold(posedge CLK, posedge D, 1.0, 1.0, notifier);
 endspecify
endmodule
module tb;
 reg CLK=0,D=0;
 wire Q;
 checked_ff dut(CLK,D,Q);
 initial begin
  #4.5 D=1; #0.5 CLK=1; #1;
  if(dut.notifier===0) $display("TIMING_CHECK_UNIMPLEMENTED");
  else $display("TIMING_CHECK_DETECTED");
  $finish;
 end
endmodule
'''
HS_PROBE = '''`timescale 1ns/1ps
module tb;
 reg CLK=0,D=0,RESET_B=0;
 wire Q;
 sky130_fd_sc_hs__dfrtp_4 dut(.CLK(CLK),.D(D),.RESET_B(RESET_B),.Q(Q));
 initial begin
  #2 RESET_B=1; #2 D=1; #2 CLK=1;
  #2 $display("HS_TIMING_VIEW_Q=%b",Q); $finish;
 end
endmodule
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_loads(log):
    if any(code in log for code in ('Error:', 'STA-1648', 'STA-1650')):
        raise RuntimeError('STA failed or extracted names do not match')
    loads = {}
    for port in PORTS:
        blocks = re.findall(r'^Net ' + re.escape(port) + r'\n(.*?)(?=^Net |\Z)',
                            log, re.M | re.S)
        if len(blocks) != 1:
            raise RuntimeError(f'Missing or duplicate interface: {port}')
        values = {}
        for label, key in [('Pin', 'pin_pf'), ('Wire', 'wire_pf'), ('Total', 'total_pf')]:
            match = re.search(r'^ ' + label + r' capacitance: ([\d.eE+-]+)$', blocks[0], re.M)
            if not match:
                raise RuntimeError(f'Missing {label} capacitance: {port}')
            values[key] = float(match[1])
        if any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise RuntimeError(f'Invalid interface capacitance: {port}')
        if not math.isclose(values['pin_pf'] + values['wire_pf'], values['total_pf'],
                            rel_tol=1e-6, abs_tol=1e-9):
            raise RuntimeError(f'Inconsistent capacitance sum: {port}')
        drivers = re.search(r'^ Number of drivers: (\d+)$', blocks[0], re.M)
        input_port = re.search(r'^ ' + re.escape(port) + r' input port ', blocks[0], re.M)
        if not drivers or int(drivers[1]) != 1 or not input_port:
            raise RuntimeError(f'Interface is not singly driven by its input port: {port}')
        loads[port] = values
    return loads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.candidate.resolve(), args.output.resolve()
    if output == root or root in output.parents:
        parser.error('Use a separate output directory to preserve the accepted candidate')
    baseline = root / 'reports_450'
    assessment = json.loads((baseline / 'assessment.json').read_text())
    inputs = {baseline / 'assessment.json': sha(baseline / 'assessment.json')}
    for section in ('sha256', 'model_sha256'):
        for name, digest in assessment[section].items():
            path = Path(name)
            if not path.is_absolute():
                path = root.parents[2] / path
            if sha(path) != digest:
                raise RuntimeError(f'Stale baseline input: {path}')
            inputs[path] = digest
    recipe = baseline / 'ss_max_timing.tcl'
    text = recipe.read_text()
    marker = '\nreport_parasitic_annotation'
    if text.count(marker) != 1:
        raise RuntimeError('Unexpected baseline STA recipe')
    prefix = text.split(marker)[0] + '\n'
    for name in re.findall(r'^(?:read_lef|read_liberty|read_db|read_spef|source) (\S+)$',
                           prefix, re.M):
        path = Path(name)
        inputs[path] = sha(path)
    libs = re.findall(r'^read_liberty (\S+)$', prefix, re.M)
    if len(libs) != 1 or not re.search(r'capacitive_load_unit\s*\(\s*1(?:\.0+)?\s*,\s*"pf"\s*\)',
                                      Path(libs[0]).read_text()):
        raise RuntimeError('Expected one library with capacitance in pF')
    libroot = Path(libs[0]).parent.parent
    if libroot.name != 'sky130_fd_sc_hs':
        raise RuntimeError('HS timing-view probe requires an HS candidate')
    timing_views = [libroot / 'verilog/primitives.v', libroot / 'verilog/sky130_fd_sc_hs.v',
                    root.parents[2] / 'verification/timing450/hs_sim_helpers.v']
    for path in timing_views:
        inputs[path] = sha(path)
    for path in (recipe, Path(__file__).resolve(), Path(__file__).with_name('run.py'),
                 Path(TOOLS['openroad']), Path('/usr/bin/iverilog'), Path('/usr/bin/vvp')):
        inputs[path] = sha(path)
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / 'assessment.json'
    receipt.unlink(missing_ok=True)
    sdf = output / 'route.ss_max.sdf'
    sdf.unlink(missing_ok=True)
    tcl = output / 'interfaces.tcl'
    tcl.write_text(prefix + ''.join(f'report_net -digits 9 {{{p}}}\n' for p in PORTS)
                   + f'write_sdf -include_typ -digits 6 -no_timestamp -no_version {{{sdf}}}\nexit\n')
    log = output / 'interfaces.log'
    run('openroad', ['-exit', tcl], log)
    loads = parse_loads(log.read_text())
    sdf_text = sdf.read_text()
    sdf_sections = {name: len(re.findall(r'\(' + name + r'\b', sdf_text))
                    for name in ('INTERCONNECT', 'IOPATH', 'SETUP', 'HOLD', 'RECOVERY', 'REMOVAL', 'WIDTH')}
    if any(count == 0 for count in sdf_sections.values()):
        raise RuntimeError('Exported SDF lacks expected delay or timing-check sections')
    probe = output / 'timing_check.v'
    probe.write_text(PROBE)
    run('/usr/bin/iverilog', ['-g2012', '-gspecify', '-s', 'tb', '-o', output / 'probe', probe],
        output / 'compile.log')
    run('/usr/bin/vvp', [output / 'probe'], output / 'probe.log')
    probe_log = (output / 'probe.log').read_text()
    detected = 'TIMING_CHECK_DETECTED' in probe_log
    if detected == ('TIMING_CHECK_UNIMPLEMENTED' in probe_log):
        raise RuntimeError('Timing-check probe did not produce a unique result')
    version = subprocess.run(['/usr/bin/iverilog', '-V'], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, check=True).stdout
    (output / 'simulator_version.log').write_text(version)
    hs_probe = output / 'hs_ff.v'
    hs_probe.write_text(HS_PROBE)
    with (output / 'hs_compile.log').open('w') as out:
        compile_result = subprocess.run([
            '/usr/bin/iverilog', '-g2012', '-gspecify', '-DUNIT_DELAY=', '-s', 'tb',
            '-o', str(output / 'hs_probe'), *map(str, timing_views), str(hs_probe)],
            cwd=REPO, stdout=out, stderr=subprocess.STDOUT)
    hs_log = (output / 'hs_compile.log').read_text()
    for path, digest in inputs.items():
        if sha(path) != digest:
            raise RuntimeError(f'Inputs changed during characterization: {path}')
    artifacts = [tcl, log, sdf, probe, output / 'compile.log', output / 'probe.log',
                 output / 'simulator_version.log', hs_probe, output / 'hs_compile.log']
    receipt.write_text(json.dumps({
        'candidate': str(root), 'target_mhz': 450,
        'scope': 'SS/1.60 V/100 C, maximum extracted RC',
        'input_loads_pf': loads, 'sdf_sections': sdf_sections,
        'sdf_export_pass': True, 'intentional_setup_violation_detected': detected,
        'hs_timing_view_compile_exit_code': compile_result.returncode,
        'hs_delayed_signals_unsupported': 'Timing checks are not supported' in hs_log,
        'timed_gate_simulation_pass': False, 'release_qualified': False, 'selected': False,
        'remaining': ['Loaded analog interface slew/pulse characterization',
                      'Timing-check-capable simulator and qualified cell timing views',
                      'Full required PVT and mode coverage'],
        'sha256': {str(p): h for p, h in inputs.items()},
        'artifact_sha256': {str(p): sha(p) for p in artifacts},
    }, indent=2) + '\n')
    print(json.dumps({'input_loads_pf': loads, 'sdf_export_pass': True,
                      'intentional_setup_violation_detected': detected}))


if __name__ == '__main__':
    main()
