"""Build an explicitly unqualified retained-C control for RC comparisons.

Original capacitor endpoints remain anchored at their C-only names. This
constructs an accounting control, not a physical distributed-capacitance model.
"""
import argparse
import hashlib
import json
from pathlib import Path
from common_v3 import save, sha, verify
from audit_keeper_native_R_contraction import compare


def record(line):
    words = line.split()
    return words[0] if words and not words[0].startswith('*') else ''


def digest_cards(path, capacitors):
    result = hashlib.sha256()
    count = 0
    with path.open() as stream:
        for line in stream:
            name = record(line)
            if name and (name[0].upper() == 'C') == capacitors:
                result.update(line.encode())
                count += 1
    return result.hexdigest(), count


def assemble(reference, candidate, destination):
    reference_headers = reference_ends = copied = dropped = headers = ends = 0
    with candidate.open() as source, destination.open('x') as target:
        target.write('* ACCOUNTING CONTROL: original C-only endpoints retained; physical C placement unqualified.\n')
        for line in source:
            name = record(line)
            if name.lower() == '.subckt':
                headers += 1
            if name and name[0].upper() == 'C':
                dropped += 1
                continue
            if name.lower() == '.ends':
                ends += 1
                with reference.open() as capacitors:
                    for original in capacitors:
                        first = record(original)
                        reference_headers += first.lower() == '.subckt'
                        reference_ends += first.lower() == '.ends'
                        if first and first[0].upper() == 'C':
                            target.write(original)
                            copied += 1
            target.write(line)
    if (headers, ends, reference_headers, reference_ends) != (1, 1, 1, 1) or not copied:
        raise ValueError('one flat reference and candidate subcircuit required')
    ref_digest = digest_cards(reference, True)
    actual_digest = digest_cards(destination, True)
    native_digest = digest_cards(candidate, False)
    retained_digest = digest_cards(destination, False)
    if ref_digest != actual_digest or native_digest != retained_digest:
        raise ValueError('literal C or native non-C records changed')
    return dict(original_C_cards_copied=copied, native_export_C_cards_replaced=dropped,
                literal_original_C_card_text_sha256=ref_digest[0],
                native_non_C_record_text_sha256=native_digest[0],
                original_C_literals_and_endpoints_preserved=True,
                native_device_R_and_port_records_preserved=True)


def run(flat, pilot, audit, output):
    receipts = [p / 'assessment.json' for p in (flat, pilot, audit)]
    a, b, g = [json.loads(p.read_text()) for p in receipts]
    closure = {}
    for r in (a, b, g):
        for path, value in {**r['input_sha256'], **r['artifacts']}.items():
            if path in closure and closure[path] != value:
                raise ValueError('conflicting prerequisite identities')
            closure[path] = value
    verify(closure)
    reference, native = flat / 'capacitance.spice', pilot / 'pilot.spice'
    if not b['native_process_completed'] or not g['primitive_and_port_contraction_preserved']:
        raise ValueError('completed primitive/port-preserving native pilot required')
    if not g['numerical_lineage']['exported_rnode_records_match']:
        raise ValueError('matching completed numerical lineage required')
    if g['input_sha256'].get(str(native)) != sha(native) or g['input_sha256'].get(str(reference)) != sha(reference):
        raise ValueError('matching audited native and reference networks required')
    pins = {str(p): sha(p) for p in [*receipts, reference, native, Path(__file__).resolve(),
                                    Path(__file__).with_name('audit_keeper_native_R_contraction.py'),
                                    Path(__file__).with_name('native_spice_comments.py')]}
    output.mkdir(parents=True, exist_ok=False)
    try:
        control = output / 'retained_C_control.spice'
        literal = assemble(reference, native, control)
        metrics = compare(reference.read_text(), control.read_text())
        if not metrics['exact_device_and_C_contraction_verified'] or metrics['negative_candidate_C_cards'] or metrics['wire_R_cards'] != g['contraction']['wire_R_cards']:
            raise ValueError('accounting control does not preserve exact reference contraction')
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256={**closure, **pins},
                                              artifacts={str(control): sha(control)}, **literal,
                                              contraction=metrics, charge_conservation_verified=True,
                                              capacitor_endpoint_policy='unchanged original C-only node names; no spatial remapping',
                                              retained_C_anchor_control=True, physical_C_mapping_qualified=False,
                                              native_export_bug_fixed=False, distributed_wire_R_qualified=False,
                                              native_simulation_allowed=False, model_qualified=False, release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('flat', 'pilot', 'audit', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.flat.resolve(), a.pilot.resolve(), a.audit.resolve(), a.output.resolve())
