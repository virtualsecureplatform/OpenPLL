"""Retain placed control buffers and add only newly localized original-net failures."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify


def run(frame, prior, localization, output):
    receipts = [p/'assessment.json' for p in (frame, prior, localization)]
    f, p, l = [json.loads(path.read_text()) for path in receipts]
    for record in (f, p, l):
        verify(record['input_sha256']); verify(record['artifacts'])
    if (not f['assembly_frame_pass'] or not p['control_buffer_composition_proved']
            or p['candidate_source_sha256'] != f['candidate_source_sha256']
            or l['input_sha256'].get(str(receipts[0])) != sha(receipts[0])
            or l['violations_with_macro_port'] != l['violations']):
        raise ValueError('matched frame, identity-proved prior plan and localized failures required')
    plan = prior/'placement_plan.json'; records = localization/'records.json'
    targets = {row['net']: dict(net=row['net'], macro_ports=[row['port']],
                repair_target_reason='retain_previous_buffer')
               for row in json.loads(plan.read_text())}
    retained = len(targets)
    for row in json.loads(records.read_text()):
        ports = row['macro_ports']
        if len(ports) != 1 or ports[0]['instance'] != 'oscillator':
            raise ValueError('one original DCO control receiver required')
        port = ports[0]
        if port['net'] in targets or port['net'].startswith('prototype_control_'):
            raise ValueError('already-buffered failure requires a different repair')
        targets[port['net']] = dict(net=port['net'], macro_ports=[port],
            repair_target_reason='new_localized_antenna_failure',
            observation=dict(stage=row['stage'], cluster=row['cluster']))
    if len(targets) <= retained:
        raise ValueError('new measured targets required')
    pins = {str(path): sha(path) for path in (*receipts, plan, records, Path(__file__).resolve())}
    verify(pins); output.mkdir(parents=True, exist_ok=False)
    target = output/'records.json'; save(target, [targets[n] for n in sorted(targets)])
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(target): sha(target)},
        record_semantics='cumulative_repair_plan_not_current_failure_count',
        retained_buffer_targets=retained, new_measured_targets=len(targets)-retained,
        repair_targets=len(targets), violations=len(targets), violations_with_macro_port=len(targets),
        antenna_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('frame', 'prior', 'localization', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, n).resolve() for n in ('frame', 'prior', 'localization', 'output')))
