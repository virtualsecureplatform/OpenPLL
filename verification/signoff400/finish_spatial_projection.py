"""Wait for the exact projection controller, then reduce only a successful pass."""
import argparse
import json
from pathlib import Path
import os
import time
from common import save, sha
from resources import identity
from reduce_spatial_sparse_runs import run as reduce_runs


def run(projection, controls, merger_upgrade, output):
    projection, controls, merger_upgrade, out = (p.resolve() for p in
        (projection, controls, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    owner = json.loads((projection/'owner.json').read_text())
    process = owner['pid']
    birth = identity(process)
    config = projection/'config.json'
    deadline = json.loads(config.read_text())['deadline_uptime']
    source = Path(__file__).with_name('reduce_spatial_sparse_runs.py')
    paths = [source, Path(__file__).resolve(), controls/'assessment.json', merger_upgrade/'assessment.json']
    pins = {str(p): sha(p) for p in paths}
    save(out/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         projection_controller_pid=process, projection_controller_birth=birth,
         automatic_identical_retry=False))
    save(out/'input_manifest.json', dict(input_sha256=pins))
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    try:
        if birth is not None:
            status('waiting_for_exact_projection_controller', pid=process, birth=birth)
            while identity(process) == birth:
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('projection wait reached the original check deadline')
                time.sleep(10)
        receipt = projection/'assessment.json'
        if not receipt.exists():
            raise ValueError('projection controller terminated without a successful assessment')
        report = json.loads(receipt.read_text())
        if not report['spatial_operator_projection_complete'] or not report['full_operator_coverage']:
            raise ValueError('full projection completion proof required')
        for path, digest in pins.items():
            if sha(Path(path)) != digest:
                raise ValueError('validated reduction input changed while projection was running')
        status('reducing_completed_full_spatial_projection')
        reduce_runs(projection, controls, out/'reduction', merger_upgrade)
        assessment = out/'reduction/assessment.json'
        result = json.loads(assessment.read_text())
        if not result['upper_triangle_sparse_matrix_reduced']:
            raise ValueError('complete sparse reduction proof required')
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(assessment): sha(assessment)},
             full_operator_projection_and_sparse_reduction_complete=True,
             scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
             global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
        status('projection_and_sparse_reduction_complete_physical_checks_pending')
    except BaseException as error:
        status('stopped_without_promotion', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('projection', 'controls', 'merger-upgrade', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.projection, args.controls, args.merger_upgrade, args.output)
