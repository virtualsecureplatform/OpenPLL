"""Changed-algorithm full projection with byte tasks; requires a failed terminal predecessor."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from common import save, sha
from compiled_charge import execute
from resources import lease, identity


def require_terminal_failed_predecessor(predecessor):
    predecessor = predecessor.resolve()
    owner = json.loads((predecessor/'owner.json').read_text())
    child = json.loads((predecessor/'native.process.json').read_text())
    if identity(owner['pid']) is not None or identity(child['pid']) == child['birth']:
        raise RuntimeError('predecessor controller or native projection is still live; duplicate full run refused')
    if (predecessor/'assessment.json').exists():
        raise RuntimeError('predecessor already has a complete projection assessment; duplicate full run refused')
    state = json.loads((predecessor/'status.json').read_text())
    if state.get('state') != 'failed':
        raise RuntimeError('explicit terminal failed predecessor status required')
    return {str(p): sha(p) for p in (predecessor/'owner.json', predecessor/'native.process.json', predecessor/'status.json')}


def run(compiled, controls, output, range_controls, predecessor):
    predecessor_pins = require_terminal_failed_predecessor(predecessor)
    compiled, controls, out = (p.resolve() for p in (compiled, controls, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    range_controls = range_controls.resolve()
    deadline = start+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-spatial-charge-', dir='/tmp'))
    (out/'native').symlink_to(scratch/'native', target_is_directory=True)
    save(out/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()), predecessor=str(predecessor.resolve()), started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False, cpu_slots=16, memory_limit_GiB=32,
         retained_local_scratch=str(scratch), changed_algorithm='shared_maps_dynamic_byte_range_projection_64_tasks_per_source'))

    def status(state, **extra):
        save(out/'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,
                                     release_qualified=False, **extra))
    try:
        receipt, proof = compiled/'assessment.json', controls/'assessment.json'
        c, checked = (json.loads(p.read_text()) for p in (receipt, proof))
        if not checked['streamed_sparse_accumulation_controls_pass']:
            raise ValueError('matching streamed sparse controls required')
        control_cfg = controls/'stream.config.json'
        base = json.loads(control_cfg.read_text())
        manifest = compiled/'operators_manifest.json'
        if sha(manifest) != c['artifacts'][str(manifest)]:
            raise ValueError('compiled operator manifest changed')
        metadata = json.loads(manifest.read_text())
        R_index = Path(base['geometry']['R_index']).parent/'assessment.json'
        R_report = json.loads(R_index.read_text())
        R_map = Path(R_report['source_mapping'])/'assessment.json'
        if sha(R_map) != R_report['input_sha256'][str(R_map)]:
            raise ValueError('runtime R field map changed')
        if json.loads(R_map.read_text())['input_sha256'].get(str(receipt)) != sha(receipt):
            raise ValueError('runtime geometry and full C compiler lineage mismatch')
        old_binary = controls/'stream_project_charge'
        range_proof = range_controls/'assessment.json'
        ranged = json.loads(range_proof.read_text())
        if not all(ranged[k] for k in ('byte_range_projection_controls_pass', 'geometry_loader_included_in_CPU_bound', 'node_maps_identical', 'all_sparse_contribution_counts_identical', 'gap_and_overlap_partitions_rejected')):
            raise ValueError('complete resource-correct byte-range controls required')
        binary = range_controls/'stream_project_charge_v2'
        expected = dict(checked['input_sha256'])
        expected.update({str(p): checked['artifacts'][str(p)] for p in (old_binary, control_cfg)})
        expected.update(ranged['input_sha256'])
        expected.update(predecessor_pins)
        expected[str(range_proof)] = sha(range_proof)
        expected[str(binary)] = ranged['artifacts'][str(binary)]
        expected[str(manifest)] = c['artifacts'][str(manifest)]
        expected.update({str(p): sha(p) for p in (receipt, proof, R_index, R_map, Path(__file__).resolve())})
        shards = []
        for spec in metadata['shards']:
            operators, mapping = Path(spec['operators']), Path(spec['field_map'])
            worker = operators.parent/'assessment.json'
            expected[str(worker)] = c['artifacts'][str(worker)]
            if sha(worker) != expected[str(worker)]:
                raise ValueError('compiled worker receipt changed')
            w = json.loads(worker.read_text())
            expected[str(operators)] = w['artifacts'][str(operators)]
            expected[str(mapping)] = c['artifacts'][str(mapping)]
            size = operators.stat().st_size
            if size < 64:
                raise ValueError('full native source too small for 64 nonempty byte tasks')
            for task in range(64):
                shards.append(dict(operators=str(operators), field_map=str(mapping), begin_byte=size*task//64, end_byte=size*(task+1)//64))
        if len(metadata['shards']) != 16 or len(shards) != 1024 or not c['all_ranges_compiled']:
            raise ValueError('complete sixteen-shard compiler input required')
        if shutil.disk_usage(scratch).free < 128*1024**3:
            raise ValueError('local sparse-run scratch reserve unavailable')
        with lease(16, 32, deadline):
            status('hashing_complete_native_operator_inputs', total_files=len(expected))
            with ThreadPoolExecutor(max_workers=16) as pool:
                jobs = {pool.submit(sha, Path(path)): path for path in expected}
                for completed, future in enumerate(as_completed(jobs), 1):
                    path = jobs[future]
                    if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                        raise TimeoutError('full projection input hashing deadline')
                    if future.result() != expected[path]:
                        raise ValueError('full spatial projection input changed: '+path)
                    status('hashing_complete_native_operator_inputs', completed_files=completed, total_files=len(expected))
            save(out/'input_manifest.json', dict(input_sha256=expected))
            geometry = base['geometry']
            geometry['deadline_uptime'] = deadline
            cfg = out/'config.json'
            save(cfg, dict(geometry=geometry, shards=shards, output=str(scratch/'native'), threads=16,
                 max_accumulator_entries=1000000, cache_limit_bytes_per_thread=33554432,
                 max_records_per_shard=0, expected_operators=c['counts']['operators'], deadline_uptime=deadline))
            status('projecting_all_830933570_native_operators', local_sparse_output=str(scratch/'native'))
            execute(['env', 'OMP_THREAD_LIMIT=16', binary, cfg], out/'native.log', deadline, 32)
            summary = json.loads((out/'native.log').read_text())
            if not summary['full_operator_coverage'] or summary['operators'] != c['counts']['operators'] or summary['byte_range_tasks'] != 1024 or not summary['disjoint_gap_free_byte_partitions_validated']:
                raise ValueError('full spatial projection operator coverage mismatch')
            status('rehashing_full_inputs_after_projection')
            with ThreadPoolExecutor(max_workers=16) as pool:
                for path, actual in zip(expected, pool.map(sha, map(Path, expected))):
                    if actual != expected[path]:
                        raise ValueError('full projection input changed during execution: '+path)
            runs = sorted((scratch/'native').glob('shard_*_run_*.bin'))
            if len(runs) != summary['sparse_runs']:
                raise ValueError('complete sparse-run set required')
            files = [*runs, scratch/'native/R_nodes.jsonl', scratch/'native/floating_nodes.jsonl',
                     cfg, out/'native.log', out/'input_manifest.json']
            status('hashing_all_completed_spatial_sparse_runs', sparse_runs=len(runs))
            with ThreadPoolExecutor(max_workers=16) as pool:
                artifacts = dict(zip(map(str, files), pool.map(sha, files)))
            save(out/'run_manifest.json', dict(runs=[dict(path=str(p), sha256=artifacts[str(p)]) for p in runs],
                 format='SPCRUN01_le_upper_u32_pair_x87_80bit_value_absolute_u64_terms',
                 coefficient_units='retained_native_capacitance_units', global_voltage_nodes=summary['global_voltage_nodes']))
            artifacts[str(out/'run_manifest.json')] = sha(out/'run_manifest.json')
            save(out/'assessment.json', dict(**summary, input_sha256=expected, artifacts=artifacts,
                 spatial_operator_projection_complete=True, external_sparse_reduction_complete=False,
                 scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
                 global_passivity_qualified=False, runtime_model_eligible=False,
                 retained_local_scratch=str(scratch)))
            status('all_native_operators_projected_sparse_reduction_pending', sparse_runs=len(runs))
            print(json.dumps(summary))
    except BaseException as error:
        status('failed', reason=repr(error), retained_local_scratch=str(scratch))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('compiled', 'controls', 'output', 'range-controls', 'predecessor'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.compiled, args.controls, args.output, args.range_controls, args.predecessor)
