#!/usr/bin/env python3
"""Candidate functional checks, without changing selected RTL or live campaigns."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from run import DEFAULT_PDK, FLOW, REPO, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hd')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    parser.add_argument('--stage', choices=['rtl', 'divider', 'mapping', 'physical', 'gate'], required=True)
    parser.add_argument('--handoff-control-proof', type=Path,
                        help='Compose unresolved handoff control comparisons with a joint gate-level induction proof')
    args = parser.parse_args()
    if args.handoff_control_proof and args.stage != 'physical':
        parser.error('--handoff-control-proof requires --stage physical')
    if args.handoff_control_proof:
        args.handoff_control_proof = args.handoff_control_proof.resolve()
    root = REPO / 'build/timing450' / args.library
    if args.stage in ('physical', 'gate'):
        assessment = 'physical_assessment.json' if args.stage == 'physical' else 'gate_assessment.json'
        (root / assessment).unlink(missing_ok=True)
    snapshot = root / 'rtl_snapshot'
    if args.stage == 'gate':
        # Reuse the independent oscillator/loop model and public-interface
        # assertions; synthesized netlists do not retain RTL observability
        # wires. This is functional gate simulation without SDF delays.
        text = (REPO / 'tb/tb_acquiring_core.v').read_text()
        begin = text.index('    // TUNING_APPLIED')
        end = text.index('    always @(posedge tracking) begin', begin)
        text = text[:begin] + text[end:]
        text = re.sub(r'        if\(dut\.local_coarse[^\n]*\n            \$fatal[^\n]*\n', '', text)
        text = text.replace(' || dut.fine_reset_n!==0', '')
        text = text.replace(' #(.DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT))', '')
        text = text.replace('acquiring_core=pass', 'timing450_gate=pass')
        bench = root / 'tb_gate.v'
        bench.write_text(text)
        scl = 'sky130_fd_sc_' + args.library
        models = Path(args.pdk_root) / 'sky130A/libs.ref' / scl / 'verilog'
        executable = root / 'gate_sim'
        with (root / 'gate_regression.log').open('w') as output:
            subprocess.run(['iverilog', '-g2012', '-DFUNCTIONAL', '-DUNIT_DELAY=', '-s', 'tb_acquiring_core',
                            '-o', str(executable), str(bench), str(root / 'route.v'),
                            str(models / 'primitives.v'), str(models / (scl + '.v')),
                            *([str(FLOW / 'hs_sim_helpers.v')] if args.library == 'hs' else [])],
                           cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)
            for phase in [7, 0]:
                subprocess.run(['vvp', str(executable), f'+PHASE_NS={phase}'],
                               cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)
        inputs = [root / 'route.v', bench, models / 'primitives.v', models / (scl + '.v'),
                  FLOW / 'verify.py', root / 'gate_regression.log']
        if args.library == 'hs':
            inputs.append(FLOW / 'hs_sim_helpers.v')
        (root / 'gate_assessment.json').write_text(json.dumps({
            'functional_pass': True, 'phases_ns': [7, 0], 'sdf_delays': False,
            'release_qualified': False,
            'sha256': {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
        }, indent=2) + '\n')
        return
    if args.stage == 'rtl':
        with (root / 'pipeline_tests.log').open('w') as output:
            for top in ['tb_timing450_graydecode', 'tb_timing450_scanstage']:
                executable = root / top
                subprocess.run(['iverilog', '-g2012', '-s', top, '-o', str(executable),
                                str(FLOW / 'tb_pipeline.v'), str(snapshot / 'IntegerPLL_FrequencyAcquisition.v')],
                               cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)
                subprocess.run(['vvp', str(executable)], cwd=REPO, stdout=output,
                               stderr=subprocess.STDOUT, check=True)
        # The existing system regression includes independent divider models,
        # reset/CDC tests, all five modes, mode changes and disturbance recovery.
        run('make', ['-f', root / 'Makefile', 'check-frequency-acquisition'], root / 'rtl_regression.log')
        return
    if args.stage == 'divider':
        gold = FLOW / 'reference_mmd.v'
        gate = snapshot / 'IntegerPLL_MMD_Retimer.v'
        top = 'IntegerPLL_MMD_Retimer'
        parameters = 'chparam -set RATIO_WIDTH 5 -set REGISTER_CONFIG 1 -set COUNTDOWN 1 -set CONFIG_PIPELINE 1 ' + top + '\n'
        library = ''
    else:
        # Prove mapping against pre-map logic, then physical repair against
        # that proven mapping using explicit original FF correspondence.
        gold = root / ('mapped.v' if args.stage == 'physical' else 'pre_map.v')
        gate = root / ('mapped.v' if args.stage == 'mapping' else 'route.v')
        top = 'IntegerPLL_AcquiringCore'
        parameters = ''
        scl = 'sky130_fd_sc_' + args.library
        lib = Path(args.pdk_root) / 'sky130A/libs.ref' / scl / 'lib' / (scl + '__tt_025C_1v80.lib')
        library = f'read_liberty -ignore_miss_func -ignore_miss_dir {lib}\n'
        if args.library == 'hs':
            library += f'read_verilog {FLOW / "hs_formal_helpers.v"}\n'
    physical_aliases = set()
    if args.stage == 'physical':
        # OpenROAD compresses internal bus aliases when unused bits disappear.
        # They are not stable state correspondence. Match the original FF
        # instances at their Q pins and compare every external port instead.
        raw = ''
        for label, source in [('gold', gold), ('gate', gate)]:
            raw += library + f'''read_verilog {source}
hierarchy -top {top}
proc
write_json {root}/physical_{label}_raw.json
design -reset
'''
        raw_recipe = root / 'physical_raw.ys'
        raw_recipe.write_text(raw)
        run('yosys', ['-s', raw_recipe], root / 'physical_raw.log')
        designs = {label: json.loads((root / f'physical_{label}_raw.json').read_text()) for label in ['gold', 'gate']}
        modules = {label: design['modules'][top] for label, design in designs.items()}
        drivers = {label: {name.lstrip('\\'): cell for name, cell in module['cells'].items()
                           if 'Q' in cell['connections']} for label, module in modules.items()}
        missing = set(drivers['gold']) - set(drivers['gate'])
        if missing:
            raise RuntimeError(f'Original state instances removed: {sorted(missing)}')
        correspondence = {}
        for index, name in enumerate(sorted(drivers['gold'])):
            alias = f'formal_state_{index}'
            physical_aliases.add(alias)
            correspondence[alias] = name
            for label in ['gold', 'gate']:
                modules[label]['netnames'][alias] = {'hide_name': 0, 'bits': drivers[label][name]['connections']['Q'], 'attributes': {}}
        for label, design in designs.items():
            (root / f'physical_{label}_aliases.json').write_text(json.dumps(design))
        (root / 'physical_comparison_contract.json').write_text(json.dumps(
            {'ports': sorted(modules['gold']['ports']), 'state_instances': correspondence,
             'reference': str(gold), 'candidate': str(gate)}, indent=2) + '\n')
    script = ''
    for label, source in [('gold', gold), ('gate', gate)]:
        loader = f'read_json {root}/physical_{label}_aliases.json\n' if args.stage == 'physical' else library + f'read_verilog {source}\n'
        script += loader + parameters + f'''hierarchy -top {top}
flatten
proc
techmap -autoproc -map +/simcells.v
# Collapse clock buffers and constant connections before sampling clocks.
# Otherwise equivalent physical clock branches become unrelated sampled
# states, preventing induction across the derived-clock boundary.
opt
write_json {root}/{args.stage}_{label}_before_clocks.json
clk2fflogic
opt
rename {top} {label}
write_json {root}/{args.stage}_{label}.json
design -stash {label}
'''
    # Materialize both sides to reject accidental matches of generated cell
    # internals, while retaining every shared RTL signal and output comparison.
    preparation = root / (args.stage + '_prepare.ys')
    preparation.write_text(script)
    run('yosys', ['-s', preparation], root / (args.stage + '_prepare.log'))
    nets = []
    for label in ['gold', 'gate']:
        module = json.loads((root / f'{args.stage}_{label}.json').read_text())['modules'][label]
        nets.append(set(module['netnames']))
    excluded = sorted(n for n in nets[0] & nets[1]
                      if n.lstrip('\\').startswith('$') or '.$' in n or n.endswith(('.IQ', '.IQ_N'))
                      or '.gen_therm[' in n)
    if args.stage == 'physical':
        keep = set(modules['gold']['ports']) | physical_aliases
        excluded = sorted((nets[0] & nets[1]) - keep)
    blacklist = root / (args.stage + '_blacklist.txt')
    blacklist.write_text('\n'.join(excluded) + '\n')
    # Infer common structures from the pre-mapping reference, after excluding
    # generated aliases; retained RTL signals and all ports remain compared.
    structural = 'equiv_struct\n'
    script += f'''design -copy-from gold -as gold gold
design -copy-from gate -as gate gate
equiv_make -blacklist {blacklist} gold gate equiv
hierarchy -top equiv
{structural}equiv_simple
equiv_induct -seq 6
equiv_status{'' if args.handoff_control_proof else ' -assert'}
'''
    recipe = root / (args.stage + '_equivalence.ys')
    recipe.write_text(script)
    proof_log = root / (args.stage + '_equivalence.log')
    run('yosys', ['-s', recipe], proof_log)
    status = re.search(r'Of those cells (\d+) are proven and (\d+) are unproven', proof_log.read_text())
    if not status:
        raise RuntimeError('Formal log lacks a completed comparison result')
    direct_proven, unresolved = map(int, status.groups())
    composed_states = []
    control_inputs = []
    if unresolved:
        if not args.handoff_control_proof:
            raise RuntimeError('Formal comparison remains unresolved')
        control = json.loads(args.handoff_control_proof.read_text())
        for required in ('functional_control_equivalence_pass', 'reset_initialized',
                         'arbitrary_synchronized_requests', 'all_original_control_states_compared'):
            if control.get(required) is not True:
                raise RuntimeError(f'Incomplete control proof: {required}')
        for name, digest in control['sha256'].items():
            path = Path(name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f'Stale control proof input: {path}')
            control_inputs.append(path)
        for path in (gold, gate, root / 'mapped.json', lib, FLOW / 'verify_handoff_control.py'):
            if control['sha256'].get(str(path)) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise RuntimeError(f'Control proof does not cover this comparison: {path}')
        gold_contract = control['contracts']['gold']
        gate_contract = control['contracts']['gate']
        from verify_handoff_control import state_instances
        expected_states, expected_request = state_instances(json.loads((root / 'mapped.json').read_text())['modules'][top])
        if (gold_contract['state_instances'] != expected_states or
                gold_contract['request_instance'] != expected_request or
                gold_contract['state_bits'] != sum(map(len, expected_states.values())) or
                gold_contract['clock_origin'] != ['port', 'PLLOUT', 0, 0]):
            raise RuntimeError('Control proof does not compare the original destination state/interface')
        control_log = args.handoff_control_proof.parent / 'proof.log'
        if ('Induction step proven: SUCCESS!' not in control_log.read_text() or
                control['sha256'].get(str(control_log)) != hashlib.sha256(control_log.read_bytes()).hexdigest()):
            raise RuntimeError('Control proof lacks a pinned unbounded induction result')
        if (gold_contract['state_instances'] != gate_contract['state_instances'] or
                gold_contract['clock_origin'] != gate_contract['clock_origin'] or
                gold_contract['reset_origin'] != gate_contract['reset_origin']):
            raise RuntimeError('Control proof interfaces do not correspond')
        permitted = {name for names in gold_contract['state_instances'].values() for name in names}
        unresolved_aliases = re.findall(r'Unproven \$equiv .*?:\s+\\?(formal_state_\d+)_gold\s+\\?\1_gate', proof_log.read_text())
        if len(unresolved_aliases) != unresolved:
            raise RuntimeError('Unresolved non-state comparison cannot use control composition')
        composed_states = [correspondence.get(alias) for alias in unresolved_aliases]
        if any(name not in permitted for name in composed_states):
            raise RuntimeError('Unresolved comparison lies outside the proven control cone')
    inputs = [gold, gate, recipe, proof_log, FLOW / 'verify.py', blacklist, *control_inputs]
    if composed_states:
        inputs.append(args.handoff_control_proof)
    if args.stage != 'divider':
        inputs.append(lib)
        if args.library == 'hs':
            inputs.append(FLOW / 'hs_formal_helpers.v')
    (root / (args.stage + '_assessment.json')).write_text(json.dumps({
        'functional_equivalence_pass': True, 'proven_cells': direct_proven + unresolved,
        'direct_equivalence_proven_cells': direct_proven,
        'joint_control_proven_state_instances': composed_states,
        'release_qualified': False,
        'sha256': {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
