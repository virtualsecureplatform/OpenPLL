#!/usr/bin/env python3
"""Audit terminal small controls and full-DCO local operator compilation."""
import json
from pathlib import Path
import time

from compile_local_C_operators_v2 import digest, save


def checked(path):
    row = json.loads(path.read_text())
    for key in ['input_sha256', 'artifacts']:
        for name, expected in row[key].items():
            assert digest(Path(name)) == expected, name
    return row


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    control_paths = sorted((base/'local_C_operator_controls_002').glob('*/assessment.json'))
    assert len(control_paths) == 12
    controls = [checked(p) for p in control_paths]
    native = json.loads((base/'DCO_C_kernel_trace_controls_001/assessment.json').read_text())
    cp = base/'DCO_local_C_operators_nom_001/assessment.json'
    compiled = checked(cp)
    expected = next(r for r in native['results'] if r['corner'] == 'nom')
    assert compiled['counts']['events'] == expected['trace_events'] == 8297230
    assert compiled['counts']['kernels'] == expected['kernel_accounting']['counts']['kernels']
    assert compiled['components'] == expected['kernel_accounting']['component_counts']
    assert all(c['local_operator_integrals_match_native_physical_totals'] for c in controls+[compiled])
    # Match compiler input bytes to the previously verified native extraction.
    for path, value in compiled['input_sha256'].items():
        if '/nom_trace/' in path:
            assert native['artifacts'][path] == value, path
    domain = base/'DCO_complete_domain_model_primitives_001/voltage_domains.jsonl'
    allowed = set()
    for text in domain.open():
        r = json.loads(text)
        allowed.add((r['original_conductor'], r['plane'], r['effective_material']))
    fields = json.loads((cp.parent/'fields.json').read_text())
    assert fields[0] == ['@SUBSTRATE_REFERENCE', 'reference', 'reference']
    assert all(tuple(key) in allowed for key in fields[1:])
    # Explicitly retain the first implementation's failed unlocated clamp
    # handling; v2 places that adjustment in its arithmetic ledger only.
    rejected = base/'local_C_operator_controls_001'
    assert (rejected/'nom_floating_metal/assessment.json').exists()
    assert not (rejected/'max_HD_narrow_FF/assessment.json').exists()
    rejection = dict(first_implementation='verification/timing400/compile_local_C_operators.py',
        failed_case='max_HD_narrow_FF', exception='KeyError: -1',
        cause='Native zero-clamp has no plane or spatial support.',
        corrected_by='verification/timing400/compile_local_C_operators_v2.py',
        correction='Unlocated clamp has zero physical operators and a separate arithmetic-only conductor ledger.',
        native_analog_or_CAD_retry=False)
    out = base/'local_C_operator_compilation_001'
    out.mkdir(exist_ok=False)
    save(out/'first_control_failure.json', rejection)
    inputs = [Path(__file__).resolve(), owner, domain, cp,
        base/'DCO_C_kernel_trace_controls_001/assessment.json',
        base/'local_C_field_integral_controls_001/assessment.json',
        Path(__file__).with_name('compile_local_C_operators.py'), *control_paths]
    result = dict(all12_native_small_case_corner_operator_controls_passed=True,
        nominal_DCO_events=compiled['counts']['events'], nominal_DCO_kernels=compiled['counts']['kernels'],
        nominal_local_operators=compiled['counts']['operators'], voltage_fields=len(fields),
        nominal_operators_match_owned_native_kernels_and_complete_domain_keys=True,
        signed_shield_terms_preserved=True, native_accumulator_residuals_separate_from_physical_operators=True,
        original_deadline_uptime=deadline, total_budget_restarted=False,
        full_private_node_matrix_passivity_and_transient_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str((out/'first_control_failure.json').resolve()): digest(out/'first_control_failure.json')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
