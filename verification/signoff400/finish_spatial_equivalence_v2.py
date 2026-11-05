"""Continue a successful projection/reduction with the full conductor check."""
import argparse
import json
import os
from pathlib import Path
import time
from common import save, sha
from resources import identity
from verify_spatial_conductor_equivalence import run as verify_equivalence


def run(followup, mapping, audit, controls, reference, comparator, merger_upgrade, output):
    followup, mapping, audit, controls, reference, comparator, merger_upgrade, out = (p.resolve() for p in
        (followup, mapping, audit, controls, reference, comparator, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    owner = json.loads((followup/'owner.json').read_text())
    process, birth = owner['pid'], owner['birth']
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    source = Path(__file__).with_name('verify_spatial_conductor_equivalence.py')
    paths = [Path(__file__).resolve(), source, followup/'owner.json',
             *[p/'assessment.json' for p in (mapping, audit, controls, reference, comparator, merger_upgrade)]]
    pins = {str(p): sha(p) for p in paths}
    save(out/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         watched_reduction_followup_pid=process, watched_reduction_followup_birth=birth,
         automatic_identical_retry=False, waiting_budget_s=172800, equivalence_check_budget_s=43200))
    save(out/'input_manifest.json', dict(input_sha256=pins))
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False, **extra))
    try:
        status('waiting_for_exact_projection_reduction_followup', pid=process, birth=birth)
        while identity(process) == birth:
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('wait for two bounded upstream checks expired')
            time.sleep(10)
        receipt = followup/'assessment.json'
        if not receipt.exists() or not json.loads(receipt.read_text())['full_operator_projection_and_sparse_reduction_complete']:
            raise ValueError('upstream projection/reduction did not publish complete success')
        for path, value in pins.items():
            if sha(Path(path)) != value:
                raise ValueError('validated equivalence source changed while waiting')
        status('verifying_full_spatial_conductor_equivalence')
        verify_equivalence(followup/'reduction', mapping, audit, controls, reference, comparator, merger_upgrade, out/'equivalence')
        result = out/'equivalence/assessment.json'
        if not json.loads(result.read_text())['full_spatial_conductor_collapse_matches_physical_integral_reference']:
            raise ValueError('full spatial/native physical-integral equivalence proof required')
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(result): sha(result)},
             full_spatial_physical_integral_equivalence_complete=True,
             full_printed_native_matrix_reconstruction_verified=False,
             scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
             global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
        status('spatial_physical_integral_equivalence_complete_other_physical_gates_pending')
    except BaseException as error:
        status('stopped_without_promotion', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('followup', 'mapping', 'audit', 'controls', 'reference', 'comparator', 'merger-upgrade', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.followup, args.mapping, args.audit, args.controls, args.reference, args.comparator, args.merger_upgrade, args.output)
