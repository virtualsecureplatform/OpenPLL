"""Check full spatial C against all physical native scalar integrals under P^T C P."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import tempfile
import time
from common import save, sha, verify
from compiled_charge import execute
from resources import lease, identity
from bind_projection_namespace import bind_namespace


def run(reduction, mapping, audit, controls, reference, comparator, merger_upgrade, output, interval_reference, interval_controls):
    reduction, mapping, audit, controls, reference, comparator, merger_upgrade, out = (p.resolve() for p in
        (reduction, mapping, audit, controls, reference, comparator, merger_upgrade, output))
    interval_reference, interval_controls = interval_reference.resolve(), interval_controls.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=8,memory_GiB=16,automatic_identical_retry=False))
    scratch = Path(tempfile.mkdtemp(prefix='openpll-spatial-conductor-equivalence-', dir='/tmp'))
    (out/'native').symlink_to(scratch, target_is_directory=True)
    def status(state, **extra):
        save(out/'status.json', dict(state=state, retained_local_scratch=str(scratch), release_qualified=False, **extra))
    try:
        interval_receipt = interval_reference/'assessment.json'
        interval_trace = interval_reference/'trace.report.json'
        interval_control_receipt = interval_controls/'assessment.json'
        interval = json.loads(interval_receipt.read_text())
        ic = json.loads(interval_control_receipt.read_text())
        if interval.get('complete_source_task_reference_intervals_certified') is not True or ic.get('interval_reference_comparator_controls_pass') is not True:
            raise ValueError('complete independent reference intervals and controlled comparator required')
        verify(ic['input_sha256'])
        receipts = [p/'assessment.json' for p in (reduction, mapping, audit, controls, reference, comparator, merger_upgrade)]
        r, m, a, c, ref, cmp, upgrade = [json.loads(p.read_text()) for p in receipts]
        if not r['upper_triangle_sparse_matrix_reduced'] or not c['spatial_conductor_collapse_controls_pass']:
            raise ValueError('complete spatial reduction and controlled collapse required')
        if not a['all_field_and_voltage_conductor_ids_independently_checked'] or a['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
            raise ValueError('matching full conductor map audit required')
        projection = Path(r['source_projection'])
        parent = projection/'assessment.json'
        p = json.loads(parent.read_text())
        if interval['input_sha256'].get(str(parent)) != sha(parent) or interval['operators'] != p['operators']:
            raise ValueError('independent interval source differs from current projection')
        bridge_pins = bind_namespace(projection, mapping)
        if not p['spatial_operator_projection_complete'] or not p['full_operator_coverage'] or not (m['source_projection'] == str(projection) or bridge_pins):
            raise ValueError('matching complete native spatial projection required')
        if r['input_sha256'].get(str(parent)) != sha(parent) or r['global_voltage_nodes'] != m['voltage_nodes']:
            raise ValueError('projection/reduction/conductor map identity mismatch')
        map_cfg = mapping/'config.json'
        cfg = json.loads(map_cfg.read_text())
        # The map was prepared while projection ran. Reconcile closed startup files
        # against the FINAL successful producer assessment before using its map.
        for key in ('R_nodes', 'floating_nodes'):
            source = Path(cfg[key])
            if bridge_pins.get(str(source)) != m['input_sha256'][str(source)]:
                raise ValueError('completed projection node-map lineage differs')
        if ref['input_sha256'].get(str(receipts[1])) != sha(receipts[1]) or cmp['input_sha256'].get(str(receipts[4])) != sha(receipts[4]):
            raise ValueError('physical reference/conductor map/comparator lineage mismatch')
        if not cmp['matrix_comparator_identity_and_clamp_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
            raise ValueError('controlled comparator and hardened sparse merger required')
        binary, compare_binary, merger = controls/'collapse_spatial_matrix', interval_controls/'compare_sparse_interval_reference', Path(upgrade['merger_binary'])
        matrix, voltage_map, expected_matrix = Path(r['final_matrix']), mapping/'native/voltage_nets.bin', Path(ref['physical_integral_reference_matrix'])
        expected = {str(binary): c['artifacts'][str(binary)], str(compare_binary): ic['artifacts'][str(compare_binary)],
             str(merger): upgrade['input_sha256'][str(merger)], str(matrix): r['artifacts'][str(matrix)],
             str(voltage_map): m['artifacts'][str(voltage_map)], str(expected_matrix): ref['artifacts'][str(expected_matrix)]}
        expected.update(bridge_pins)
        expected[str(interval_trace)] = interval['artifacts'][str(interval_trace)]
        paths = list(dict.fromkeys([*receipts, parent, map_cfg, interval_receipt, interval_control_receipt, *map(Path, expected), Path(__file__).resolve()]))
        with lease(8, 16, deadline):
            status('hashing_full_spatial_equivalence_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins = dict(zip(map(str, paths), pool.map(sha, paths)))
            if any(pins[path] != value for path, value in expected.items()):
                raise ValueError('full spatial equivalence input changed')
            collapse_cfg = out/'collapse.json'
            save(collapse_cfg, dict(matrix=str(matrix), voltage_map=str(voltage_map), threads=8,
                 max_accumulator_entries=1000000, output=str(scratch/'runs'), deadline_uptime=deadline))
            status('collapsing_every_spatial_matrix_coefficient_to_original_conductors')
            execute([binary, collapse_cfg], out/'collapse.log', deadline, 16)
            summary = json.loads((out/'collapse.log').read_text())
            current = sorted((scratch/'runs').glob('*.bin'))
            if len(current) != summary['sparse_runs'] or not current or summary['conductor_nets'] != ref['conductor_nets']:
                raise ValueError('complete conductor-collapse runs required')
            artifacts = {str(path): sha(path) for path in current}
            level = 0
            while len(current) > 1:
                groups = [current[i:i+64] for i in range(0, len(current), 64)]
                tasks = []
                for number, group in enumerate(groups):
                    config = scratch/f'level_{level}_group_{number}.json'
                    result = scratch/f'level_{level}_group_{number}.bin'
                    log = scratch/f'level_{level}_group_{number}.log'
                    save(config, dict(inputs=list(map(str, group)), output=str(result), deadline_uptime=deadline))
                    tasks.append((config, log, result))
                status('reducing_collapsed_spatial_matrix', level=level, groups=len(groups))
                with ThreadPoolExecutor(max_workers=8) as pool:
                    jobs = [pool.submit(execute, [merger, config], log, deadline, 1) for config, log, _ in tasks]
                    for future in as_completed(jobs):
                        future.result()
                for config, log, result in tasks:
                    for path in (config, log, result):
                        artifacts[str(path)] = sha(path)
                current = [result for _, _, result in tasks]
                level += 1
            collapsed = current[0]
            compare_cfg, comparison = out/'compare.json', out/'comparison.json'
            save(compare_cfg, dict(left=str(expected_matrix), right=str(collapsed),
                 node_count=ref['conductor_nets'], interval_reference_report=str(interval_trace), absolute_tolerance=1e-8, relative_tolerance=2e-12,
                 require_match=True, report=str(comparison), deadline_uptime=deadline))
            status('comparing_with_all_physical_native_capacitor_integrals')
            execute([compare_binary, compare_cfg], out/'compare.log', deadline, 2)
            result = json.loads(comparison.read_text())
            if not result['within_tolerance']:
                raise ValueError('spatial/native physical-integral equivalence failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha, paths)) != list(pins.values()):
                    raise ValueError('equivalence input changed during verification')
            for path in (collapse_cfg, out/'collapse.log', compare_cfg, comparison, out/'compare.log', collapsed):
                artifacts[str(path)] = sha(path)
            save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
                 source_upper_entries=summary['source_upper_entries'], collapsed_matrix=str(collapsed),
                 full_spatial_conductor_collapse_matches_physical_integral_reference=True,
                 comparison_scope='unfolded abstract reference; original scalar matrix with exact source-derived reference intervals at (0,0) and (0,1)',
                 independent_exact_reference_intervals_used=True, original_scalar_reference_preserved=True, reference_zero_retained=True,
                 completed_projection_node_maps_reconciled=True, full_printed_native_matrix_reconstruction_verified=False,
                 scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
                 global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
            status('full_spatial_physical_integral_equivalence_verified_other_physical_gates_pending')
    except BaseException as error:
        status('failed', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reduction', 'mapping', 'audit', 'controls', 'reference', 'comparator', 'merger-upgrade', 'output', 'interval-reference', 'interval-controls'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.reduction, args.mapping, args.audit, args.controls, args.reference, args.comparator, args.merger_upgrade, args.output, args.interval_reference, args.interval_controls)
