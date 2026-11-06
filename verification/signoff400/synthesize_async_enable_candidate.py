"""Map the isolated asynchronous-enable proposal without replacing selected RTL.

The mapped state correspondence and capture-chain wiring are checked separately.
Placement, routing, physical CDC and source-to-layout binding remain open.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
sys.path.insert(0, str(ROOT/'verification/timing400'))
from check_compact_mapping import ALLOWED, LIB, YOSYS


def capture_chain(module):
    nets = module['netnames']
    pipe = nets['enable_ref_pipe']
    q = pipe['bits']
    if len(q) != 2 or len(set(q)) != 2 or pipe['attributes'].get('ASYNC_REG') != 'TRUE':
        raise ValueError('mapped two-bit ASYNC_REG capture net required')
    cells = []
    for index in range(2):
        drivers = [(name, c) for name, c in module['cells'].items()
                   if c['connections'].get('Q') == [q[index]]]
        if len(drivers) != 1:
            raise ValueError('unique mapped stage driver required')
        name, cell = drivers[0]
        if not cell['type'].startswith('sky130_fd_sc_hs__dfrtp_'):
            raise ValueError('positive-edge asynchronous-clear capture cell required')
        expected = dict(D=module['ports']['PLL_ENABLE']['bits'] if index == 0 else [q[0]],
                        CLK=module['ports']['REFCLK']['bits'],
                        RESET_B=nets['ref_reset_n']['bits'], Q=[q[index]])
        if cell['connections'] != expected:
            raise ValueError('mapped capture data/clock/reset wiring changed')
        cells.append(dict(stage=index, instance=name, master=cell['type'], connections=expected))
    if nets['enable_ref']['bits'] != [q[1]]:
        raise ValueError('startup enable alias must remain the second stage')
    return cells


def run(candidate, review, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {27})
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        catalog = candidate/'sources.json'
        c, reviewed = [json.loads(p.read_text()) for p in (catalog, review)]
        verify(c['basis_input_sha256'])
        verify(reviewed['input_sha256'])
        for key in ('candidate_two_stage_reference_capture_verified',
                    'first_stage_tap_and_reset_polarity_mutants_rejected',
                    'sampled_handoff_reset_contract_proven',
                    'logical_clear_seed_recovery_before_unmask_proven'):
            if reviewed[key] is not True:
                raise ValueError('candidate-specific logic review required: '+key)
        sources = sorted(candidate.glob('*.v'))
        if len(sources) != 9 or reviewed['input_sha256'].get(str(catalog)) != sha(catalog):
            raise ValueError('exact reviewed nine-source candidate required')
        for p in sources:
            if c['source_sha256'].get(str(p.relative_to(ROOT))) != sha(p):
                raise ValueError('candidate catalog identity differs')
            if reviewed['input_sha256'].get(str(p)) != sha(p):
                raise ValueError('review does not bind actual candidate source')
        frozen = output/'rtl'
        frozen.mkdir()
        for p in sources:
            shutil.copyfile(p, frozen/p.name)
        actual = sorted(p for p in frozen.glob('*.v') if p.name != 'IntegerPLL_400MHz_PrototypeTop.v')
        source_pins = {str(p): sha(p) for p in frozen.glob('*.v')}
        save(output/'sources.json', dict(files=[str(p.relative_to(output)) for p in actual],
            physical_top='rtl/IntegerPLL_400MHz_PrototypeTop.v'))
        helpers = ('common_v3.py', 'resources.py', 'compiled_charge_v2.py')
        paths = [catalog, review, *sources, LIB, Path(YOSYS), Path(__file__).resolve(),
                 ROOT/'verification/timing400/check_compact_mapping.py', output/'sources.json',
                 *(Path(__file__).with_name(n) for n in helpers)]
        pins = {str(p): sha(p) for p in paths}
        pins.update(source_pins)
        save(output/'inputs.json', dict(input_sha256=pins))
        def invoke(argv, log):
            verify(pins)
            with lease(1, 4, deadline):
                execute(argv, log, deadline, 4)
        masters = set(re.findall(r'cell\s*\(\s*"?([^\s"\)]+)', LIB.read_text()))
        supported = {'sky130_fd_sc_hs__'+name for name in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_4')}
        ff_exclusions = ' '.join('-dont_use '+name for name in sorted(masters)
                                 if name.startswith('sky130_fd_sc_hs__df') and name not in supported)
        mappings = []
        for label in ('full', 'compact'):
            folder = output/label
            folder.mkdir()
            excluded = {n for n in masters if 'probe' in n or 'lpflow' in n} if label == 'full' else masters-ALLOWED
            script = folder/'synth.ys'
            script.write_text(f'''read_verilog {' '.join(map(str, actual))}
hierarchy -check -top IntegerPLL_ProgrammedCore
synth -top IntegerPLL_ProgrammedCore -flatten
dfflibmap -liberty {LIB} {ff_exclusions}
abc -liberty {LIB} -D 2222 {' '.join('-dont_use '+n for n in sorted(excluded))}
hilomap -hicell sky130_fd_sc_hs__conb_1 HI -locell sky130_fd_sc_hs__conb_1 LO
clean
delete t:$scopeinfo
read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
check -assert
stat -liberty {LIB}
write_verilog -norename {folder}/mapped.v
write_json {folder}/mapped.json
''')
            save(output/'status.json', dict(state='mapping_async_enable_candidate', mapping=label, release_ready=False))
            invoke([YOSYS, '-s', script], folder/'synth.log')
            module = json.loads((folder/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
            counts = Counter(cell['type'] for cell in module['cells'].values())
            if label == 'compact' and not set(counts) <= ALLOWED:
                raise ValueError('unsupported compact mapping master')
            chain = capture_chain(module)
            save(folder/'assessment.json', dict(input_sha256=pins,
                artifacts={str(p): sha(p) for p in (script, folder/'synth.log', folder/'mapped.v', folder/'mapped.json')},
                candidate_source_sha256=source_pins, synthesis=dict(cells=sum(counts.values()), counts=dict(counts)),
                mapped_capture_chain=chain, physical_timing_qualified=False, release_ready=False))
            mappings.append(dict(label=label, cells=sum(counts.values()), capture_chain=chain))
        checker = ROOT/'verification/prototype400/check_mapping.py'
        pins[str(checker)] = sha(checker)
        proof = output/'mapping_proof'
        invoke(['/usr/bin/python3', checker, '--gold', output/'full', '--gate', output/'compact', '--output', proof], output/'mapping_proof.log')
        result = json.loads((proof/'assessment.json').read_text())
        verify(result['input_sha256'])
        verify(result['artifacts'])
        if not (result['all_transition_clock_reset_and_output_functions_equivalent']
                and result['corrupted_data_function_rejected']):
            raise ValueError('mapping equivalence and corruption control required')
        verify(pins)
        paths = [output/'sources.json', proof/'assessment.json', output/'mapping_proof.log',
                 output/'full/assessment.json', output/'compact/assessment.json']
        save(output/'assessment.json', dict(input_sha256=pins,
            artifacts={str(p): sha(p) for p in paths}, candidate_source_sha256=source_pins,
            mappings=mappings, paired_registers=result['paired_registers'],
            full_and_compact_transition_clock_reset_and_output_functions_equivalent=True,
            mapping_data_corruption_rejected=True, two_stage_capture_preserved_in_both_mappings=True,
            candidate_layout_exists=False, selected_layout_promoted=False,
            physical_CDC_qualified=False, physical_timing_qualified=False, release_ready=False))
        save(output/'status.json', dict(state='async_enable_candidate_mapped_and_proved', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'review', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.candidate.resolve(), args.review.resolve(), args.output.resolve())
