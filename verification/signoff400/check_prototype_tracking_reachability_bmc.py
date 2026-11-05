"""Bounded reachability control for an already proved configuration-stability abstraction."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS


def run(proof, output):
    baseline = proof/'baseline'
    control = proof/'tracking_reachability_control'
    source = baseline/'IntegerPLL_ProgrammedCore.v'
    mutant = control/'IntegerPLL_ProgrammedCore.v'
    original = source.read_text()
    changed = mutant.read_text()
    token = '} != f_previous_configuration'
    if changed.count(token) != 1 or changed.replace(token, '} == f_previous_configuration') != original:
        raise ValueError('reachability control must invert only the tracked stability assertion')
    log = baseline/'proof.log'
    if 'Property proved' not in log.read_text():
        raise ValueError('baseline joint assertions must already be proved')
    model = control/'model.aig'
    values = list(map(int, model.open('rb').readline().decode().split()[1:]))
    if values[5:7] != [3, 2]:
        raise ValueError('three assertions and two constraints required')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    abc = str(Path(YOSYS).with_name('yosys-abc'))
    paths = [source, mutant, log, baseline/'model.aig', model,
             control/'export.ys', control/'export.log', image, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+300
    command = ['apptainer', 'exec', '--bind', '/home:/home', image, abc, '-c',
               f'read_aiger {model}; fold; strash; bmc3 -F 200 -T 120 -v']
    with lease(1, 4, deadline):
        execute(command, output/'bmc.log', deadline, 4)
    result = (output/'bmc.log').read_text()
    verify(pins)
    if 'was asserted in frame' not in result:
        raise ValueError('bounded control did not demonstrate tracked-state reachability')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(output/'bmc.log'): sha(output/'bmc.log')},
         baseline_joint_assertions_proved=True, tracked_configuration_state_reachable=True,
         only_stability_assertion_inverted=True, conservative_core_cut_retained=True,
         initial_seed_loading_proved=False, full_core_behavior_proved=False,
         physical_timing_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('proof', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    run(a.proof.resolve(), a.output.resolve())
