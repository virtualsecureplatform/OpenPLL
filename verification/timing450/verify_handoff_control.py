#!/usr/bin/env python3
"""Prove the mapped/routed handoff control jointly, including its invariants.

The request synchronizer Q is an arbitrary input. Clock and reset buffer trees
must have identical origins and polarity before abstracting one destination
clock edge per proof step. Every original control FF and its complete D cone
is retained. No data/control combinational function is replaced.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from run import DEFAULT_PDK, FLOW, REPO, run


STATES = ('remaining', 'transfer_busy', 'capture_pending',
          'pending_request', 'acknowledge')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_instances(mapped):
    drivers = {c['connections']['Q'][0]: n.lstrip('\\')
               for n, c in mapped['cells'].items() if 'Q' in c['connections']}
    states = {name: [drivers[b] for b in mapped['netnames']['handoff.' + name]['bits']]
              for name in STATES}
    request = drivers[mapped['netnames']['handoff.request_sync']['bits'][0]]
    return states, request


def extract(design, states, request, label):
    module = design['modules']['IntegerPLL_AcquiringCore']
    cells = {n.lstrip('\\'): c for n, c in module['cells'].items()}
    for cell in cells.values():
        if 'port_directions' not in cell:
            model = design['modules'].get(cell['type'], {})
            cell['port_directions'] = {p: v['direction'] for p, v in model.get('ports', {}).items()}
        if set(cell['connections']) - set(cell['port_directions']):
            raise RuntimeError(f'Uncharacterized cell ports: {cell["type"]}')
    drivers = {}
    for name, cell in cells.items():
        for pin, direction in cell['port_directions'].items():
            if direction == 'output':
                for bit in cell['connections'][pin]:
                    if isinstance(bit, int):
                        if bit in drivers:
                            raise RuntimeError(f'Multiple drivers on {bit}')
                        drivers[bit] = (name, pin)
    ports = {b: (n, i) for n, p in module['ports'].items()
             if p['direction'] == 'input' for i, b in enumerate(p['bits'])}

    def origin(bit):
        inversion = 0
        seen = set()
        while bit in drivers:
            if bit in seen:
                raise RuntimeError('Cycle in clock/reset buffer tree')
            seen.add(bit)
            name, pin = drivers[bit]
            cell = cells[name]
            match = re.fullmatch(r'sky130_fd_sc_(?:hs|hd)__(buf|clkbuf|inv|clkinv)_[0-9]+', cell['type'])
            if not match:
                return ('cell', name, pin, inversion)
            inversion ^= match[1] in ('inv', 'clkinv')
            bit = cell['connections']['A'][0]
        if bit not in ports:
            raise RuntimeError('Clock/reset origin is not driven')
        return ('port', *ports[bit], inversion)

    names = [n for state in STATES for n in states[state]]
    if any(n not in cells for n in names + [request]):
        raise RuntimeError('Original handoff state/synchronizer instance missing')
    clock_origins = {origin(cells[n]['connections']['CLK'][0]) for n in names}
    reset_origins = {origin(cells[n]['connections']['RESET_B'][0]) for n in names}
    if clock_origins != {('port', 'PLLOUT', 0, 0)} or len(reset_origins) != 1:
        raise RuntimeError(f'Control FF clock/reset mismatch: {clock_origins}, {reset_origins}')
    state_bits = [cells[n]['connections']['Q'][0] for n in names]
    request_bit = cells[request]['connections']['Q'][0]
    boundary = set(state_bits + [request_bit])
    retained = set(names)

    def visit(bit):
        if not isinstance(bit, int) or bit in boundary:
            return
        if bit not in drivers:
            raise RuntimeError(f'Unexpected undriven control input {bit}')
        name, _ = drivers[bit]
        if name in retained:
            return
        cell = cells[name]
        if 'Q' in cell['connections']:
            raise RuntimeError(f'Unexpected register in handoff D cone: {name}')
        retained.add(name)
        for pin, direction in cell['port_directions'].items():
            if direction == 'input':
                for source in cell['connections'][pin]:
                    visit(source)

    for name in names:
        visit(cells[name]['connections']['D'][0])
    largest = max(b for c in cells.values() for bits in c['connections'].values()
                  for b in bits if isinstance(b, int))
    clock, reset = largest + 1, largest + 2
    selected = {n: copy.deepcopy(cells[n]) for n in retained}
    for n in names:
        if not re.fullmatch(r'sky130_fd_sc_(?:hs|hd)__dfrtp_[0-9]+', selected[n]['type']):
            raise RuntimeError(f'Unsupported control FF: {selected[n]["type"]}')
        selected[n]['connections']['CLK'] = [clock]
        selected[n]['connections']['RESET_B'] = [reset]
    reduced = {'attributes': {}, 'ports': {
        'CLK': {'direction': 'input', 'bits': [clock]},
        'RESET_N': {'direction': 'input', 'bits': [reset]},
        'REQUEST_SYNC': {'direction': 'input', 'bits': [request_bit]},
        'STATE': {'direction': 'output', 'bits': state_bits}},
        'cells': selected, 'netnames': {}}
    out = copy.deepcopy(design)
    del out['modules']['IntegerPLL_AcquiringCore']
    out['modules'][label + '_control'] = reduced
    return out, {'state_instances': states, 'clock_origin': list(next(iter(clock_origins))),
                 'reset_origin': list(next(iter(reset_origins))),
                 'request_instance': request, 'state_bits': len(state_bits),
                 'retained_cells': len(selected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hs')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    parser.add_argument('--negative-control-check', action='store_true',
                        help='Require a permanently-low acknowledgement mutant to fail')
    args = parser.parse_args()
    root = REPO / 'build/timing450' / args.library
    proof = root / 'handoff_control_proof'
    proof.mkdir(exist_ok=True)
    (proof / 'assessment.json').unlink(missing_ok=True)
    lib = Path(args.pdk_root) / 'sky130A/libs.ref' / ('sky130_fd_sc_' + args.library) / 'lib' / ('sky130_fd_sc_' + args.library + '__tt_025C_1v80.lib')
    helpers = [FLOW / 'hs_formal_helpers.v'] if args.library == 'hs' else []
    helper_loader = ''.join(f'read_verilog {p}\n' for p in helpers)
    raw = ''
    for label, source in [('gold', root / 'mapped.v'), ('gate', root / 'route.v')]:
        raw += (f'read_liberty -ignore_miss_func -ignore_miss_dir {lib}\n' + helper_loader +
                f'read_verilog {source}\nhierarchy -top IntegerPLL_AcquiringCore\nproc\n'
                f'write_json {proof}/{label}_raw.json\ndesign -reset\n')
    (proof / 'raw.ys').write_text(raw)
    run('yosys', ['-s', proof / 'raw.ys'], proof / 'raw.log')
    mapped = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    states, request = state_instances(mapped)
    contracts = {}
    for label in ('gold', 'gate'):
        design, contracts[label] = extract(json.loads((proof / f'{label}_raw.json').read_text()), states, request, label)
        (proof / f'{label}.json').write_text(json.dumps(design))
    if contracts['gold']['reset_origin'] != contracts['gate']['reset_origin']:
        raise RuntimeError('Mapped/routed handoff reset origins differ')
    width = contracts['gold']['state_bits']
    count = len(states['remaining'])
    wrappers = ''
    for label in ('gold', 'gate'):
        valid = "1'b1" if label == 'gold' else (
            f'((STATE[{count}] == (STATE[{count+1}] || |STATE[{count-1}:0]))) && '
            f'(!STATE[{count+1}] || STATE[{count-1}:0]==0) && '
            f'(STATE[{count}] || STATE[{count+2}]==STATE[{count+3}])')
        wrappers += (f'module {label}(input CLK,RESET_N,REQUEST_SYNC,output [{width-1}:0] STATE,output VALID);\n'
                     f'{label}_control u(.CLK(CLK),.RESET_N(RESET_N),.REQUEST_SYNC(REQUEST_SYNC),.STATE(STATE));\nassign VALID={valid};\nendmodule\n')
    (proof / 'wrappers.v').write_text(wrappers)
    recipe = ''
    for label in ('gold', 'gate'):
        recipe += (f'read_json {proof}/{label}.json\nread_verilog -formal {proof}/wrappers.v\n'
                   f'prep -top {label}\nflatten\ntechmap -autoproc -map +/simcells.v\nopt\n'
                   f'design -stash {label}\n')
    recipe += ('design -copy-from gold -as gold gold\ndesign -copy-from gate -as gate gate\n'
               'miter -equiv -flatten -make_outputs gold gate miter\nprep -top miter\n'
               'async2sync\nopt\n'
               'sat -seq 2 -tempinduct -maxsteps 30 -set-at 1 in_RESET_N 0 '
               '-set-def-inputs -prove trigger 0 -verify -show-ports\n')
    (proof / 'proof.ys').write_text(recipe)
    run('yosys', ['-s', proof / 'proof.ys'], proof / 'proof.log')
    if 'Induction step proven: SUCCESS!' not in (proof / 'proof.log').read_text():
        raise RuntimeError('Missing unbounded induction success')
    negative_checked = False
    if args.negative_control_check:
        mutant = json.loads((proof / 'gate.json').read_text())
        mutant['modules']['gate_control']['cells'][states['acknowledge'][0]]['connections']['D'] = ['0']
        (proof / 'gate_mutant.json').write_text(json.dumps(mutant))
        (proof / 'negative.ys').write_text(recipe.replace(f'{proof}/gate.json', f'{proof}/gate_mutant.json'))
        try:
            run('yosys', ['-s', proof / 'negative.ys'], proof / 'negative.log')
        except subprocess.CalledProcessError:
            if 'proof did fail' not in (proof / 'negative.log').read_text():
                raise RuntimeError('Negative check failed for a reason other than a counterexample')
            negative_checked = True
        else:
            raise RuntimeError('Incorrect acknowledgement mutant passed the proof')
    files = [root / 'mapped.v', root / 'mapped.json', root / 'route.v', lib,
             Path(__file__), *helpers, *proof.glob('*.json'), *proof.glob('*.v'),
             *proof.glob('*.ys'), *proof.glob('*.log')]
    result = {'functional_control_equivalence_pass': True, 'reset_initialized': True,
              'arbitrary_synchronized_requests': True, 'all_original_control_states_compared': True,
              'invariants_proven': ['busy equals capture or nonzero count',
                                    'capture implies zero count', 'idle implies pending equals acknowledge'],
              'contracts': contracts, 'release_qualified': False,
              'negative_control_check_pass': negative_checked,
              'sha256': {str(p): sha(p) for p in files}}
    (proof / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print('handoff_control_equivalence=pass state_bits=' + str(width))


if __name__ == '__main__':
    main()
