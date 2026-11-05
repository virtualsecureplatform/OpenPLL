"""Bounded parallel external reduction of fully projected spatial C runs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import tempfile
import time
from common import save, sha
from compiled_charge import execute
from resources import lease


def run(projection, controls, output, merger_upgrade):
    projection, controls, out = (p.resolve() for p in (projection, controls, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-spatial-reduce-', dir='/tmp'))
    (out/'native').symlink_to(scratch, target_is_directory=True)
    def status(state, **extra):
        save(out/'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,
             retained_local_scratch=str(scratch), release_qualified=False, **extra))
    try:
        receipt, proof = projection/'assessment.json', controls/'assessment.json'
        p, c = [json.loads(path.read_text()) for path in (receipt, proof)]
        if not p['spatial_operator_projection_complete'] or not p['full_operator_coverage']:
            raise ValueError('complete full native operator projection required')
        if not c['streamed_sparse_accumulation_controls_pass']:
            raise ValueError('controlled sparse merger required')
        manifest = projection/'run_manifest.json'
        if sha(manifest) != p['artifacts'][str(manifest)]:
            raise ValueError('full projection run manifest changed')
        rows = json.loads(manifest.read_text())['runs']
        upgrade_receipt=merger_upgrade.resolve()/'assessment.json'
        upgrade=json.loads(upgrade_receipt.read_text())
        if not upgrade['actual_operator_merge_bytes_identical'] or upgrade['source_stream_controls']!=str(controls):
            raise ValueError('matching validated sparse merger upgrade required')
        if upgrade['input_sha256'].get(str(proof))!=sha(proof):raise ValueError('merger upgrade stream controls changed')
        format_receipt=Path(upgrade['source_format_controls'])/'assessment.json'
        if upgrade['input_sha256'].get(str(format_receipt))!=sha(format_receipt):raise ValueError('merger format controls changed')
        if not json.loads(format_receipt.read_text())['all_sparse_format_controls_pass']:raise ValueError('adversarial format controls required')
        binary=Path(upgrade['merger_binary'])
        pins = {str(path): sha(path) for path in (receipt, proof, manifest, binary, upgrade_receipt, format_receipt, Path(__file__).resolve())}
        if pins[str(binary)] != upgrade['input_sha256'][str(binary)] or not rows:
            raise ValueError('matching merger and nonempty full run set required')
        for row in rows:
            if p['artifacts'].get(row['path']) != row['sha256']:
                raise ValueError('projection run lineage mismatch')
        with lease(8, 8, deadline):
            status('hashing_all_full_projection_runs', runs=len(rows))
            with ThreadPoolExecutor(max_workers=8) as pool:
                actual = list(pool.map(sha, (Path(row['path']) for row in rows)))
            if any(digest != row['sha256'] for digest, row in zip(actual, rows)):
                raise ValueError('completed sparse projection run changed')
            pins.update({row['path']: row['sha256'] for row in rows})
            current = [Path(row['path']) for row in rows]
            artifacts = {}
            round_number = 0
            while len(current) > 1:
                groups = [current[i:i+64] for i in range(0, len(current), 64)]
                status('reducing_sorted_sparse_runs', round=round_number, input_runs=len(current), groups=len(groups))
                tasks = []
                for number, group in enumerate(groups):
                    result = scratch/f'round_{round_number}_group_{number}.bin'
                    cfg = scratch/f'round_{round_number}_group_{number}.json'
                    log = scratch/f'round_{round_number}_group_{number}.log'
                    save(cfg, dict(inputs=list(map(str, group)), output=str(result), deadline_uptime=deadline))
                    tasks.append((cfg, log, result))
                with ThreadPoolExecutor(max_workers=8) as pool:
                    futures = {pool.submit(execute, [binary, cfg], log, deadline, 1): (cfg, log, result)
                               for cfg, log, result in tasks}
                    for done, future in enumerate(as_completed(futures), 1):
                        cfg, log, result = futures[future]
                        future.result()
                        for path in (cfg, log, result):
                            artifacts[str(path)] = sha(path)
                        status('reducing_sorted_sparse_runs', round=round_number, completed_groups=done, groups=len(groups))
                current = [result for _, _, result in tasks]
                round_number += 1
            final = current[0]
            (out/'matrix.bin').symlink_to(final)
            # Retain all intermediate runs; input verification remains meaningful after merging.
            status('verifying_reduction_inputs_unchanged')
            with ThreadPoolExecutor(max_workers=8) as pool:
                for path, digest in zip(pins, pool.map(sha, map(Path, pins))):
                    if digest != pins[path]:
                        raise ValueError('spatial reduction input changed: '+path)
            artifacts[str(final)] = sha(final)
            save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
                 final_matrix=str(final), source_projection=str(projection), input_runs=len(rows), merge_rounds=round_number,
                 upper_triangle_sparse_matrix_reduced=True, coefficient_units='retained_native_capacitance_units',
                 explicit_reference_node=0, global_voltage_nodes=p['global_voltage_nodes'],
                 scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
                 global_passivity_qualified=False, physical_RC_qualified=False, runtime_model_eligible=False,
                 resistance_PVT_qualified=False, release_qualified=False))
            status('spatial_operator_matrix_reduced_rounding_and_passivity_pending')
    except BaseException as error:
        status('failed', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('projection', 'controls', 'output', 'merger-upgrade'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.projection, args.controls, args.output, args.merger_upgrade)
