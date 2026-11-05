#!/usr/bin/env python3
"""Prove transition/output equivalence after compact physical optimization.

State correspondence uses exact instance names. Drive-strength substitutions
are permitted only after structural equality of imported functional FF models.
No physical, analog or metastability equivalence is implied.
"""
import argparse
import copy
import json
from pathlib import Path

import sys
from common import ROOT
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB, YOSYS, cut_pair, run
TOP='IntegerPLL_ProgrammedCore'
from run_dco_qualification import sha, save


def signature(module):
    cells = [dict(type=c['type'], parameters=c['parameters'],
                  port_directions=c['port_directions'], connections=c['connections'])
             for c in module['cells'].values()]
    return dict(ports=module['ports'], cells=sorted(cells, key=lambda c: json.dumps(c, sort_keys=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold-json', required=True, type=Path)
    parser.add_argument('--physical-verilog', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    gold_path, physical = args.gold_json.resolve(), args.physical_verilog.resolve()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__).resolve(), Path(YOSYS), LIB, gold_path, physical,
              ROOT/'verification/timing400/check_compact_mapping.py']
    pins = {str(p): sha(p) for p in inputs}
    task = out / 'prepare.ys'
    task.write_text(f'''read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
read_verilog {physical}
hierarchy -check -top {TOP}
write_json {out}/physical.json
design -reset
read_liberty -ignore_miss_func -ignore_miss_dir {LIB}
write_json {out}/library.json
''')
    assert run([YOSYS, '-s', task], out/'prepare.log') == 0
    library = json.loads((out/'library.json').read_text())['modules']
    gold = json.loads(gold_path.read_text())['modules'][TOP]
    gate = json.loads((out/'physical.json').read_text())['modules'][TOP]
    # OpenROAD's Verilog writer preserves the Yosys escaped instance marker
    # as a literal leading backslash. Resolve only exact golden-name matches;
    # refuse collisions rather than guessing correspondence from net order.
    renames = {}
    for name in list(gate['cells']):
        if name.startswith('\\') and name[1:] in gold['cells']:
            canonical = name[1:]
            assert canonical not in gate['cells'], canonical
            gate['cells'][canonical] = gate['cells'].pop(name)
            renames[name] = canonical
    substitutions = {}
    for module in (gold, gate):
        for cell in module['cells'].values():
            master = cell['type']
            if master.startswith(('sky130_fd_sc_hs__dfrtp_', 'sky130_fd_sc_hs__dfstp_')):
                canonical = master.rsplit('_', 1)[0] + '_1'
                assert signature(library[master]) == signature(library[canonical]), master
                substitutions[master] = canonical
                cell['type'] = canonical
    states = cut_pair(gold, gate)
    for label, module in [('CUT_GOLD', gold), ('CUT_GATE', gate)]:
        save(out/(label+'.json'), dict(modules={label:module}))
    task = out/'equivalence.ys'
    task.write_text(f'''read_liberty -ignore_miss_func -ignore_miss_dir {LIB}
read_json {out}/CUT_GOLD.json
read_json {out}/CUT_GATE.json
miter -equiv -make_outputs -flatten CUT_GOLD CUT_GATE miter
hierarchy -top miter
prep -top miter -flatten
sat -verify -prove trigger 0 -show-inputs -show-outputs
''')
    assert run([YOSYS, '-s', task], out/'equivalence.log') == 0
    assert 'SUCCESS!' in (out/'equivalence.log').read_text()
    # Corrupt an asynchronous-control function to check that those functions
    # remain observable in precisely the same proof as data and clock inputs.
    bad = copy.deepcopy(gate)
    pin = next(p for p in bad['ports'] if p.startswith('capture_') and p.endswith('_RESET_B'))
    bits = [b for c in bad['cells'].values() for v in c['connections'].values() for b in v]
    bits += [b for p in bad['ports'].values() for b in p['bits']]
    new_bit = max(b for b in bits if isinstance(b, int)) + 1
    bad['cells']['negative_reset_inverter'] = dict(type='sky130_fd_sc_hs__clkinv_1',
        parameters={}, attributes={}, port_directions={'A':'input','Y':'output'},
        connections={'A':bad['ports'][pin]['bits'], 'Y':[new_bit]})
    bad['ports'][pin]['bits'] = [new_bit]
    save(out/'CUT_BAD.json', dict(modules={'CUT_GATE':bad}))
    negative = out/'negative.ys'
    negative.write_text(task.read_text().replace(str(out/'CUT_GATE.json'),str(out/'CUT_BAD.json')))
    assert run([YOSYS, '-s', negative], out/'negative.log') != 0
    assert 'proof did fail' in (out/'negative.log').read_text()
    for path, digest in pins.items(): assert sha(Path(path)) == digest, path
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        matched_state_primitives=states, verified_ff_functional_substitutions=substitutions,
        exact_escaped_instance_aliases=renames,
        all_transition_and_output_functions_equivalent=True,
        corrupted_reset_function_rejected=True,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print(f'Equivalent transition/output functions for {states} paired state primitives', flush=True)


if __name__ == '__main__':
    main()
