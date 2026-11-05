#!/usr/bin/env python3
"""Prove the timing overlay's destination transition against the root handoff.

Run inside the pinned container. Source-domain logic must remain byte identical.
The destination proof exposes every original state bit and the busy invariant,
starts with reset, and leaves payload/request and subsequent reset unrestricted.
"""
import hashlib
import json
from pathlib import Path
import subprocess

from run import REPO, FLOW, TOOLS


def domain(source):
    start = source.index('    always @(posedge REFCLK')
    end = source.index('    always @(posedge DCOCLK')
    reference = source[start:end]
    source = source[:start] + source[end:]
    source = source.replace('output wire APPLIED',
                            'output wire [2*WIDTH+COUNT_WIDTH+8:0] STATE,\n'
                            '    output wire VALID,\n    output wire APPLIED')
    source = source.replace('input wire [WIDTH-1:0] COMMAND,',
                            'input wire [WIDTH-1:0] COMMAND,\n'
                            '    input wire [WIDTH-1:0] payload,\n'
                            '    input wire request, sent_valid, acknowledge_meta, acknowledge_sync,')
    source = source.replace('    reg [WIDTH-1:0] payload;\n', '')
    source = source.replace('    reg request, acknowledge, sent_valid;', '    reg acknowledge;')
    source = source.replace('    (* ASYNC_REG="TRUE" *) reg acknowledge_meta, acknowledge_sync;\n', '')
    valid = '(transfer_busy == (capture_pending || remaining!=0))' if 'reg transfer_busy;' in source else "1'b1"
    source = source.replace('    assign APPLIED=',
                            '    assign STATE={payload,request,acknowledge,sent_valid,request_meta,'
                            'request_sync,acknowledge_meta,acknowledge_sync,remaining,pending_request,'
                            'capture_pending,APPLIED_COMMAND};\n'
                            f'    assign VALID={valid};\n    assign APPLIED=')
    return reference, source


def main():
    root = REPO / 'build/timing450/handoff_proof'
    root.mkdir(parents=True, exist_ok=True)
    original = REPO / 'rtl/IntegerPLL_TuningHandoff.v'
    overlay = FLOW / 'rtl/IntegerPLL_TuningHandoff.v'
    gold_ref, gold = domain(original.read_text())
    gate_ref, gate = domain(overlay.read_text())
    if gold_ref != gate_ref:
        raise RuntimeError('Source-domain logic changed; compositional proof no longer applies')
    (root / 'gold.v').write_text(gold)
    (root / 'gate.v').write_text(gate)
    checks = []
    for cycles in (1, 2, 3, 4):
        recipe = ''
        for name in ('gold', 'gate'):
            recipe += (f'read_verilog -formal -sv {root}/{name}.v\n'
                       f'chparam -set WIDTH 34 -set APPLY_CYCLES {cycles} IntegerPLL_TuningHandoff\n'
                       'prep -top IntegerPLL_TuningHandoff\n'
                       f'rename IntegerPLL_TuningHandoff {name}\ndesign -stash {name}\n')
        recipe += ('design -copy-from gold -as gold gold\n'
                   'design -copy-from gate -as gate gate\n'
                   'miter -equiv -flatten -make_outputs gold gate miter\n'
                   'prep -top miter\nasync2sync\nopt\n'
                   'sat -seq 2 -tempinduct -maxsteps 30 -set-at 1 in_DCO_RESET_N 0 '
                   '-set-def-inputs -prove trigger 0 -verify -show-ports\n')
        ys = root / f'cycles_{cycles}.ys'
        log = root / f'cycles_{cycles}.log'
        ys.write_text(recipe)
        with log.open('w') as out:
            subprocess.run([TOOLS['yosys'], '-s', str(ys)], stdout=out,
                           stderr=subprocess.STDOUT, check=True)
        sim = root / f'cycles_{cycles}.vvp'
        sim_log = root / f'cycles_{cycles}_simulation.log'
        with sim_log.open('w') as out:
            subprocess.run(['iverilog', '-g2012', '-s', 'tb_tuning_handoff',
                            f'-Ptb_tuning_handoff.APPLY_CYCLES={cycles}', '-o', str(sim),
                            str(overlay), str(REPO / 'tb/tb_tuning_handoff.v')],
                           stdout=out, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['vvp', str(sim)], stdout=out, stderr=subprocess.STDOUT, check=True)
        checks.extend((ys, log, sim_log))
    inputs = [original, overlay, Path(__file__), REPO / 'tb/tb_tuning_handoff.v',
              root / 'gold.v', root / 'gate.v', *checks]
    (root / 'assessment.json').write_text(json.dumps({
        'functional_equivalence': True, 'source_domain_identical': True,
        'destination_state_and_busy_invariant_proven': True,
        'width': 34, 'apply_cycles': [1, 2, 3, 4],
        'timing_closed': False, 'release_qualified': False,
        'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }, indent=2) + '\n')
    print('handoff_equivalence=pass apply_cycles=1,2,3,4')


if __name__ == '__main__':
    main()
