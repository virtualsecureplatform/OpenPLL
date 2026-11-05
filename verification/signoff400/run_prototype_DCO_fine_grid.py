"""Measure a bounded interior grid; endpoint coverage alone does not qualify tuning."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT, save, sha, verify

def run(candidate, rc, output):
    worker = Path(__file__).with_name('run_prototype_DCO_candidate_band_probe_v2.py')
    pins = {str(p): sha(p) for p in (candidate/'assessment.json', rc/'assessment.json', worker, Path(__file__).resolve())}
    output.mkdir(parents=True, exist_ok=False)
    tasks = []
    for corner, coarse in [('tt', 20), ('ff', 9), ('ss', 47), ('sf', 26), ('fs', 20)]:
        for fine in range(24, 233, 16):
            folder = output/f'{corner}_co{coarse}_fine{fine}'
            command = ['taskset', '-c', '0-31', sys.executable, worker,
                       '--candidate', candidate, '--rc', rc, '--corner', corner,
                       '--coarse', str(coarse), '--fine', str(fine), '--output', folder]
            tasks.append((folder, list(map(str, command))))
    save(output/'input_manifest.json', dict(input_sha256=pins, point_commands=[c for _, c in tasks],
         simultaneous_point_producers=12, native_resource_leases_retained=True,
         automatic_identical_retry=False, interpolation_is_not_native_holdout_validation=True))
    def one(folder, command):
        with (output/(folder.name+'.driver.log')).open('x') as stream:
            code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
        return dict(point=str(folder), exit_code=code)
    results = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for future in as_completed([pool.submit(one, *task) for task in tasks]):
            results.append(future.result())
            save(output/'status.json', dict(state='interior_grid_running', completed_points=len(results),
                 failed_points=sum(r['exit_code'] != 0 for r in results), release_ready=False))
    verify(pins)
    detail = output/'results.json'
    save(detail, results)
    for result in results:
        if result['exit_code'] == 0:
            receipt = Path(result['point'])/'assessment.json'
            pins[str(receipt)] = sha(receipt)
    failed = sum(r['exit_code'] != 0 for r in results)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(detail):sha(detail)},
         native_points_completed=len(results)-failed, failed_points=failed,
         parent_loading_complete=False, holdout_validation_complete=False,
         analog_tuning_qualified=False, release_ready=False))
    save(output/'status.json', dict(state='interior_grid_complete' if not failed else 'interior_grid_failed',
         completed_points=len(results), failed_points=failed, release_ready=False))
    if failed:
        raise RuntimeError(f'{failed} native points failed; preserved without retry')

if __name__ == '__main__':
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'rc', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.candidate.resolve(), args.rc.resolve(), args.output.resolve())
