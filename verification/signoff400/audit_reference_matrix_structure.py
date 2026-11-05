"""Audit complete unfolded conductor matrices without granting physical qualification."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(reference, controls, output):
    reference, controls, out = reference.resolve(), controls.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+12*3600
    proof = controls/'assessment.json'
    checked = json.loads(proof.read_text())
    if not checked['matrix_structure_controls_pass'] or not checked['necessary_checks_explicitly_insufficient_for_PSD']:
        raise ValueError('matrix structure controls missing')
    executable = controls/'audit_sparse_matrix'
    if sha(executable) != checked['artifacts'][str(executable)]:
        raise ValueError('controlled auditor changed')
    prior = reference/'assessment.json'
    source = json.loads(prior.read_text())
    if not source['native_capacitor_scalar_matrix_references_prepared']:
        raise ValueError('complete reference matrices required')
    paths = [Path(__file__).resolve(), prior, proof, executable]
    matrices = {label: Path(source[key]) for label, key in (
        ('physical_integral', 'physical_integral_reference_matrix'),
        ('native_trace_delta', 'native_output_reference_matrix'))}
    paths += list(matrices.values())
    pins = {str(p): sha(p) for p in paths}
    for p in matrices.values():
        if pins[str(p)] != source['artifacts'][str(p)]:
            raise ValueError('reference matrix changed')
    results = {}
    with lease(8, 8, deadline):
        for label, matrix in matrices.items():
            cfg, report = out/(label+'.json'), out/(label+'.report.json')
            save(cfg, dict(matrix=str(matrix), node_count=source['conductor_nets'], threads=8,
                           maximum_dense_bytes=8*1024**3, deadline_uptime=deadline,
                           scaled_charge_residual_limit=1e-12, report=str(report)))
            execute([executable, cfg], out/(label+'.log'), deadline, 8)
            results[label] = json.loads(report.read_text())
        if any(sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError('reference matrix audit input changed')
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in out.glob('*.report.json')}, results=results,
             complete_reference_matrix_structure_audit=True,
             scope='unfolded ideal conductor coefficient representation; abstract reference separate from VGND',
             substrate_reference_fold_applied=False, native_printed_output_equivalence_verified=False,
             spatial_voltage_constraints_qualified=False, full_matrix_passivity_verified=False,
             global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
        print(json.dumps({k: {name: v[name] for name in (
            'upper_entries', 'maximum_scaled_charge_residual',
            'significant_negative_diagonal_records', 'significant_negative_two_by_two_minors',
            'necessary_checks_pass')} for k, v in results.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.controls, args.output)
