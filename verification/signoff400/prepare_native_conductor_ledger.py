"""Prepare physical-integral and native-output conductor C matrix references."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import tempfile
import time
from common import save, sha
from compiled_charge import execute
from resources import lease


def run(compiled, mapping, audit, controls, merger_upgrade, output):
    compiled, mapping, audit, controls, merger_upgrade, out = (p.resolve() for p in
        (compiled, mapping, audit, controls, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-native-conductor-ledger-', dir='/tmp'))
    (out/'native').symlink_to(scratch, target_is_directory=True)
    def status(state, **extra):
        save(out/'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,
             retained_local_scratch=str(scratch), release_qualified=False, **extra))
    try:
        receipts = [p/'assessment.json' for p in (compiled, mapping, audit, controls, merger_upgrade)]
        c, m, a, checked, upgrade = [json.loads(p.read_text()) for p in receipts]
        if not checked['capacitor_scalar_expansion_controls_pass']:
            raise ValueError('controlled scalar-capacitor expansion required')
        if not a['all_field_and_voltage_conductor_ids_independently_checked'] or a['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
            raise ValueError('matching independent conductor map audit required')
        if m['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
            raise ValueError('conductor maps/compiler receipt mismatch')
        if not upgrade['actual_operator_merge_bytes_identical']:
            raise ValueError('controlled sparse merger upgrade required')
        binary, merger = controls/'collapse_native_cap_ledger', Path(upgrade['merger_binary'])
        ledger, summary, fields = compiled/'collapsed_matrix_ledger.json', compiled/'merge_summary.json', mapping/'native/field_nets.bin'
        expected = {str(ledger): c['artifacts'][str(ledger)], str(summary): c['artifacts'][str(summary)],
                    str(fields): m['artifacts'][str(fields)], str(binary): checked['artifacts'][str(binary)],
                    str(merger): upgrade['input_sha256'][str(merger)]}
        expected.update(checked['input_sha256'])
        paths = [*receipts, *map(Path, expected), Path(__file__).resolve()]
        with lease(8, 16, deadline):
            status('hashing_native_ledger_reference_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins = dict(zip(map(str, paths), pool.map(sha, paths)))
            if any(pins[p] != h for p, h in expected.items()):
                raise ValueError('native reference source or controlled binary changed')
            cfg = out/'config.json'
            save(cfg, dict(ledger=str(ledger), field_map=str(fields), output=str(scratch/'runs'),
                 threads=8, max_accumulator_entries=1000000,
                 expected_rows=json.loads(summary.read_text())['global_ledger_rows'], deadline_uptime=deadline))
            status('expanding_all_native_scalar_capacitors')
            execute([binary, cfg], out/'collapse.log', deadline, 16)
            result = json.loads((out/'collapse.log').read_text())
            artifacts, final = {}, {}
            for kind in ('physical', 'native'):
                current = sorted((scratch/'runs').glob(kind+'_part_*.bin'))
                if len(current) != result[kind+'_runs'] or not current:
                    raise ValueError('complete native reference sparse runs required')
                for path in current:
                    artifacts[str(path)] = sha(path)
                level = 0
                while len(current) > 1:
                    groups = [current[i:i+64] for i in range(0, len(current), 64)]
                    tasks = []
                    for number, group in enumerate(groups):
                        config = scratch/f'{kind}_level_{level}_group_{number}.json'
                        output = scratch/f'{kind}_level_{level}_group_{number}.bin'
                        log = scratch/f'{kind}_level_{level}_group_{number}.log'
                        save(config, dict(inputs=list(map(str, group)), output=str(output), deadline_uptime=deadline))
                        tasks.append((config, log, output))
                    status('reducing_native_reference_matrix', kind=kind, level=level, groups=len(groups))
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        jobs = [pool.submit(execute, [merger, config], log, deadline, 1) for config, log, _ in tasks]
                        for future in as_completed(jobs):
                            future.result()
                    for config, log, output in tasks:
                        for path in (config, log, output):
                            artifacts[str(path)] = sha(path)
                    current = [output for _, _, output in tasks]
                    level += 1
                final[kind] = str(current[0])
                (out/(kind+'.bin')).symlink_to(current[0])
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha, paths)) != list(pins.values()):
                    raise ValueError('native reference input changed during expansion/reduction')
            artifacts[str(cfg)] = sha(cfg)
            artifacts[str(out/'collapse.log')] = sha(out/'collapse.log')
            save(out/'assessment.json', dict(**result, input_sha256=pins, artifacts=artifacts,
                 physical_integral_reference_matrix=final['physical'], native_output_reference_matrix=final['native'],
                 native_capacitor_scalar_matrix_references_prepared=True,
                 spatial_projection_equivalence_verified=False, scalar_rounding_spatial_assignment_complete=False,
                 full_C_energy_matrix_assembled=False, global_passivity_qualified=False, runtime_model_eligible=False))
            status('native_reference_matrices_prepared_spatial_equivalence_pending')
            print(json.dumps(result))
    except BaseException as error:
        status('failed', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('compiled', 'mapping', 'audit', 'controls', 'merger-upgrade', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.compiled, args.mapping, args.audit, args.controls, args.merger_upgrade, args.output)
