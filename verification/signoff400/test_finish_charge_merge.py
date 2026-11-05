"""Finalization rehashes actual native artifacts and inherits its original budget."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from common import save
from finish_charge_merge import run,require_native_artifacts
from compile_native_charge import run as compile_native
from benchmark_charge_merge import run as benchmark
from test_native_charge import source_fixture

class FinishCompiledMerge(unittest.TestCase):
    def test_missing_native_artifact_role_rejected(self):
        roles=('operators.jsonl','fields.json','collapsed_matrix_ledger.json','observed_plane_residues.json')
        require_native_artifacts(dict(artifacts={p:'fixture' for p in roles}))
        for missing in roles:
            with self.subTest(missing=missing),self.assertRaises(ValueError):
                require_native_artifacts(dict(artifacts={p:'fixture' for p in roles if p!=missing}))

    def test_real_small_shards_revalidated_without_recompilation_or_budget_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);native,_=source_fixture(root);prior=root/'prior'
            compile_native(native,prior,workers=1,wall_limit_s=240)
            merged=root/'merged';benchmark(prior,merged,memory_gib=4)
            # Simulate only the terminal-controller failure; native artifacts stay exact.
            save(prior/'status.json',dict(state='failed'))
            (prior/'merge.log').write_text('MemoryError\n')
            owner=json.loads((prior/'owner.json').read_text());deadline=owner['deadline_uptime']
            with self.assertRaisesRegex(ValueError,'not terminal'):
                run(prior,merged,root/'rejected_live')
            owner.update(pid=-100000,birth='not-live');save(prior/'owner.json',owner)
            owner['deadline_uptime']=time.clock_gettime(time.CLOCK_BOOTTIME)-1;save(prior/'owner.json',owner)
            with self.assertRaises(TimeoutError):run(prior,merged,root/'rejected_expired')
            owner['deadline_uptime']=deadline;save(prior/'owner.json',owner)
            path=native/'trace/owners.log';original=path.read_bytes();path.write_bytes(original+b'changed\n')
            with self.assertRaisesRegex(ValueError,'artifact identity mismatch'):
                run(prior,merged,root/'rejected_changed')
            path.write_bytes(original)
            out=root/'finished';run(prior,merged,out)
            report=json.loads((out/'assessment.json').read_text())
            self.assertTrue(report['all_native_inputs_and_shard_artifacts_rehashed'])
            self.assertEqual(report['recompiled_shards'],0)
            self.assertTrue(report['original_whole_check_deadline_preserved'])
            self.assertEqual(json.loads((out/'owner.json').read_text())['deadline_uptime'],deadline)
            self.assertFalse(report['runtime_model_eligible']);self.assertEqual(report['counts']['kernels'],27)
            self.assertTrue((out/'worker_0').is_symlink())
            manifest=json.loads((out/'operators_manifest.json').read_text())
            for row in manifest['shards']:
                for key in ('operators','field_map'):self.assertEqual(str(Path(row[key]).resolve()),row[key])
