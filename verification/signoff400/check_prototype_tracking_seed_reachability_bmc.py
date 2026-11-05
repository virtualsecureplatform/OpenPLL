"""Bounded reachability control for the proved full-core initial seed and configuration properties."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS
from prove_prototype_tracking_configuration_v2 import instrument


def run(proof, candidate, output):
    baseline = proof/'baseline'
    control = proof/'tracked_seed_reachability_control'
    source = baseline/'IntegerPLL_ProgrammedCore.v'
    mutant = control/'IntegerPLL_ProgrammedCore.v'
    original = source.read_text()
    changed = mutant.read_text()
    token = 'core_dco_code != fine_seed'
    if changed.count(token) != 1 or changed.replace(token, 'core_dco_code == fine_seed') != original:
        raise ValueError('reachability control must invert only the initial tracked seed assertion')
    candidate_receipt=candidate/'assessment.json'
    selected=json.loads(candidate_receipt.read_text())
    verify(selected['candidate_source_sha256'])
    actual=candidate/'rtl/IntegerPLL_ProgrammedCore.v'
    if instrument(actual.read_text(),False)!=original or instrument(actual.read_text(),True)!=changed:
        raise ValueError('actual full-core instrumentation differs')
    if original.count('IntegerPLL_DigitalCore #(')!=1 or 'f_free_feedback_clock' in original:
        raise ValueError('actual core must be retained')
    log = baseline/'proof.log'
    if 'Property proved' not in log.read_text():
        raise ValueError('baseline joint assertions must already be proved')
    model = control/'model.aig'
    values = list(map(int, model.open('rb').readline().decode().split()[1:]))
    if values[5:7] != [4, 2]:
        raise ValueError('four assertions and two constraints required')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    abc = str(Path(YOSYS).with_name('yosys-abc'))
    paths = [source, mutant, log, baseline/'model.aig', model,
             control/'export.ys', control/'export.log', baseline/'export.ys', baseline/'export.log',
             candidate_receipt,*map(Path,selected['candidate_source_sha256']),
             Path(__file__).with_name('prove_prototype_tracking_configuration_v2.py'),image,Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    command = ['apptainer', 'exec', '--bind', '/home:/home', image, abc, '-c',
               f'read_aiger {model}; fold; strash; bmc3 -F 512 -T 300 -v']
    with lease(1, 4, deadline):
        execute(command, output/'bmc.log', deadline, 4)
    result = (output/'bmc.log').read_text()
    verify(pins)
    if 'was asserted in frame' not in result:
        raise ValueError('bounded control did not demonstrate tracked-state reachability')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(output/'bmc.log'): sha(output/'bmc.log')},
         baseline_joint_assertions_proved=True, tracked_seed_state_reachable=True,
         candidate_source_sha256=selected['candidate_source_sha256'],
         only_initial_seed_assertion_inverted=True, actual_full_core_and_both_handoffs_retained=True,
         initial_sampled_tracking_code_matches_seed_proved=True,
         configuration_stable_during_sampled_tracking_proved=True, full_core_behavior_proved=False,
         physical_timing_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('proof', 'candidate', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    run(a.proof.resolve(), a.candidate.resolve(), a.output.resolve())
