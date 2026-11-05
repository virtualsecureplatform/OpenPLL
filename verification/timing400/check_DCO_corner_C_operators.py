#!/usr/bin/env python3
"""Audit all three terminal DCO operator streams against frozen native traces."""
import json
from pathlib import Path
import time
from check_local_C_operator_compilation import checked
from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    native_path = base/'DCO_C_kernel_trace_controls_001/assessment.json'
    native = json.loads(native_path.read_text())
    assert native['full_DCO_trace_accounting_passed']
    domain = base/'DCO_complete_domain_model_primitives_001/voltage_domains.jsonl'
    allowed = set()
    for line in domain.open():
        r = json.loads(line)
        allowed.add((r['original_conductor'], r['plane'], r['effective_material']))
    receipts, results = [], {}
    for corner in ['min', 'nom', 'max']:
        path = base/f'DCO_local_C_operators_{corner}_001/assessment.json'
        r = checked(path)
        expected = next(item for item in native['results'] if item['corner'] == corner)
        assert r['local_operator_integrals_match_native_physical_totals']
        assert r['counts']['events'] == expected['trace_events']
        assert r['counts']['kernels'] == expected['kernel_accounting']['counts']['kernels']
        assert r['components'] == expected['kernel_accounting']['component_counts']
        for name, value in r['input_sha256'].items():
            if f'/{corner}_trace/' in name:
                assert native['artifacts'][name] == value, name
        fields = json.loads((path.parent/'fields.json').read_text())
        assert fields[0] == ['@SUBSTRATE_REFERENCE', 'reference', 'reference']
        assert all(tuple(k) in allowed for k in fields[1:])
        results[corner] = dict(counts=r['counts'], voltage_fields=len(fields),
            all_fields_in_complete_voltage_atlas=True,
            all_kernel_integrals_match_recorded_native_physical_totals=True,
            native_trace_bytes_match_preceding_verified_extraction=True,
            arithmetic_residual_absolute_native_cap_units=r['arithmetic_residual_absolute_native_cap_units'])
        receipts.append(path)
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base/'DCO_corner_C_operators_001'
    out.mkdir(exist_ok=False)
    inputs = [Path(__file__).resolve(), owner, native_path, domain, *receipts,
        Path(__file__).with_name('check_local_C_operator_compilation.py')]
    save(out/'assessment.json', dict(all_three_RC_corner_operator_integrals_and_ownership_passed=True,
        results=results, full_private_node_corner_matrices_assembled=False,
        signed_global_passivity_and_transient_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs}, artifacts={}))
    print(json.dumps({c: dict(events=r['counts']['events'], operators=r['counts']['operators'], fields=r['voltage_fields'])
        for c, r in results.items()}, indent=2))


if __name__ == '__main__':
    main()
